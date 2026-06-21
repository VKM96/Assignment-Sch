import selectors
import socket
import logging
import ssl
import os
import jwt
from server_config import server_config 
from enum import Enum

CLIENT_AUTH_TOKEN_PREFIX = "AUTH "
SERVER_AUTH_OK_RESPONSE = "OK: AUTH_SUCCESS"
SERVER_ERROR_RESPONSE = "SERVER: ERROR"

SERVER_NW_BUF_SIZE = 65535

class Protocol(Enum):
    TCP = "TCP"
    UDP = "UDP"
    TLS = "TLS"

selector = selectors.DefaultSelector()

def verify_jwt_token(token: str, jwt_secret, jwt_algorithm) -> tuple[bool, str | None]:
    """
    Verify the JWT token and return (success, client_id).
    success = True if valid, False otherwise.
    client_id = extracted client_id claim if valid, None otherwise.
    """
    try:
        decoded_token = jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm])
        client_id = decoded_token.get("client_id", "unknown")
        return True, client_id
    except jwt.ExpiredSignatureError:
        logging.error("JWT token has expired.")
        return False, None
    except jwt.InvalidTokenError:
        logging.error("Invalid JWT token.")
        return False, None
    
def validate_payload(data: bytes, max_size: int) -> tuple[bool, str | None, str | None]:
    # Reject oversized payloads
    if len(data) > max_size:
        reason = (f"Payload too large ({len(data)} bytes)")
        return False, None, reason

    try:
        validated_data = data.decode("utf-8")
    except UnicodeDecodeError:
        reason = (f"Malformed/binary payload rejected")
        return False, None, reason

    return True, validated_data, None

def socket_close(client_socket, proto: Protocol, address = "unknown"):
    """Safely close sockets without crashing"""
    try:
        selector.unregister(client_socket)
    except Exception:
        pass
    try:
        client_socket.close()
    except Exception:
        pass
    logging.info(f"Closed {proto.value} connection with {address}")


def tcp_server_start(host, port, max_connections):
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind((host, port))
    tcp_socket.listen(max_connections)
    tcp_socket.setblocking(False)

    selector.register(tcp_socket, selectors.EVENT_READ, tcp_connection_handler)
    logging.info(f"TCP Server listening on {host}:{port}")
    return tcp_socket

def tcp_connection_handler(tcp_socket):
    connection, address = tcp_socket.accept()
    connection.setblocking(False)

    selector.register(connection, selectors.EVENT_READ, lambda sock: stream_data_handler(sock, Protocol.TCP, address))
    logging.info(f"TCP Connection from {address}")

def tls_server_start(host, port, max_connections, tls_cert_path, tls_key_path):
    tls_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tls_socket.bind((host, port))
    tls_socket.listen(max_connections)
    tls_socket.setblocking(False)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    os.makedirs(server_config["cert_dir"], exist_ok=True)
    context.load_cert_chain(certfile=tls_cert_path, keyfile=tls_key_path)

    # wrap the TCP socket with SSL context and register it with the selector
    selector.register(tls_socket, selectors.EVENT_READ, lambda sock: tls_connection_handler(sock, context))
    logging.info(f"TLS Server listening on {host}:{port}")
    return tls_socket

def tls_connection_handler(tcp_socket, context):
    connection, address = tcp_socket.accept()
    try:
        connection = context.wrap_socket(connection, server_side=True)
        logging.info(f"TLS Connection from {address}")
        # Perform authentication by expecting an "AUTH <token>" message from the client
        auth_message = connection.recv(512).decode().strip()
        logging.info(f"TLS<< {auth_message}")

        if not auth_message.startswith(CLIENT_AUTH_TOKEN_PREFIX):
            logging.error(f"Authentication failed with {address}: No AUTH message received")
            socket_close(connection, Protocol.TLS, address)
            return

        token = auth_message[len(CLIENT_AUTH_TOKEN_PREFIX):].strip()
        is_success, client_id = verify_jwt_token(token, server_config["jwt_secret"], server_config["jwt_algorithm"])
        if not is_success:
            logging.error(f"Authentication failed with {address}: Invalid JWT token")
            socket_close(connection, Protocol.TLS, address)
            return
        logging.info(f"TLS client {client_id} authenticated from {address}")
        
        logging.info(f"TLS>> {SERVER_AUTH_OK_RESPONSE}")
        connection.sendall(SERVER_AUTH_OK_RESPONSE.encode())
        connection.setblocking(False)
        selector.register(connection, selectors.EVENT_READ, lambda sock: stream_data_handler(sock, Protocol.TLS, address))

    except ssl.SSLError as e:
        logging.error(f"TLS handshake failed with {address}: {e}")
        socket_close(connection, Protocol.TLS, address)

def udp_server_start(host, port):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((host, port))
    udp_socket.setblocking(False)
    selector.register(udp_socket, selectors.EVENT_READ, udp_connection_handler)
    logging.info(f"UDP Server listening on {host}:{port}")
    return udp_socket

def udp_connection_handler(udp_socket):
    try:
        data, address = udp_socket.recvfrom(SERVER_NW_BUF_SIZE)
        common_data_handler(Protocol.UDP, udp_socket, data, address)
    except Exception as e:
        socket_close(udp_socket, Protocol.UDP, "<unknown>")

def stream_data_handler(client_socket, proto: Protocol, address):
    try:
        data = client_socket.recv(SERVER_NW_BUF_SIZE)
        if data:
            common_data_handler(proto, client_socket, data, address)
        else:
            logging.info(f"!{address} disconnected")
            socket_close(client_socket, proto, address)
    except Exception as e:
        logging.error(f"{proto.value} error with {address}: {e}")
        socket_close(client_socket, proto, address)

def common_data_handler(proto: Protocol, client_socket, data, address):
    """
    proto: Protocol enum (Protocol.TCP, Protocol.UDP, Protocol.TLS)
    sock: socket object (for TCP/TLS) or udp_socket (for UDP)
    data: bytes received
    addr: (ip, port) tuple
    """

    Is_valid_data, validated_data, reason = validate_payload(data, int(server_config["max_payload"]))

    if not Is_valid_data:
        logging.warning(f"{proto.value} : {address} : {reason}")

        if proto == Protocol.UDP:
            return
        else:
            try:
                client_socket.sendall(f"{SERVER_ERROR_RESPONSE}: {reason}\n".encode())
            except Exception:
                pass
            socket_close(client_socket, proto, address)
        return

    logging.info(f"<< {proto.value} << {address}: {validated_data}")

    if proto == Protocol.UDP:
        client_socket.sendto(data, address)
    else:
        client_socket.sendall(data)

    logging.info(f">> {proto.value} >> {address}: {validated_data}")


def tcp_udp_server(server_config):

    host = server_config["host"]
    tcp_port = int(server_config["tcp_port"])
    udp_port = int(server_config["udp_port"])
    tls_port = int(server_config["tls_port"])
    tls_cert_path = os.path.join(server_config["cert_dir"], server_config["cert_file"])
    tls_key_path = os.path.join(server_config["cert_dir"], server_config["key_file"])

    max_connections = int(server_config["max_connections"])

    tcp_server_start(host, tcp_port, max_connections)     # TCP Socket    
    udp_server_start(host, udp_port)     # UDP Socket
    tls_server_start(host, tls_port, max_connections, tls_cert_path, tls_key_path)  # TLS Socket

    logging.info("Server is running. Waiting for connections..., Press Ctrl+C to stop the server.")

    try:
        while True:
            events = selector.select(timeout=1) 
            for key, mask in events:
                callback = key.data
                callback(key.fileobj)   
    except KeyboardInterrupt:
        logging.info("Exit Signal received. Server is shutting down.")
    finally:
        selector.close()
        logging.info("All sockets closed.")

if __name__ == "__main__":
    tcp_udp_server(server_config)