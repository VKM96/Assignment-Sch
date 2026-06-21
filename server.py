from logging import config
from multiprocessing import context
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
SERVER_PAYLOAD_BUF_SIZE = 4096

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

    selector.register(connection, selectors.EVENT_READ, lambda sock: stream_data_handler(sock, Protocol.TCP))
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
            connection.close()
            return

        token = auth_message[len(CLIENT_AUTH_TOKEN_PREFIX):].strip()
        is_success, client_id = verify_jwt_token(token, server_config["jwt_secret"], server_config["jwt_algorithm"])
        if not is_success:
            logging.error(f"Authentication failed with {address}: Invalid JWT token")
            connection.close()
            return
        logging.info(f"TLS client {client_id} authenticated from {address}")
        
        logging.info(f"TLS>> {SERVER_AUTH_OK_RESPONSE}")
        connection.sendall(SERVER_AUTH_OK_RESPONSE.encode())
        connection.setblocking(False)
        selector.register(connection, selectors.EVENT_READ, lambda sock: stream_data_handler(sock, Protocol.TLS))

    except ssl.SSLError as e:
        logging.error(f"TLS handshake failed with {address}: {e}")
        connection.close()

def udp_server_start(host, port):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((host, port))
    udp_socket.setblocking(False)
    selector.register(udp_socket, selectors.EVENT_READ, udp_connection_handler)
    logging.info(f"UDP Server listening on {host}:{port}")
    return udp_socket

def udp_connection_handler(udp_socket):
    data, address = udp_socket.recvfrom(SERVER_PAYLOAD_BUF_SIZE)
    common_data_handler(Protocol.UDP, udp_socket, data, address)

def stream_data_handler(client_socket, proto: Protocol):
    try:
        data = client_socket.recv(SERVER_PAYLOAD_BUF_SIZE)
        if data:
            common_data_handler(proto, client_socket, data, address = client_socket.getpeername())
        else:
            logging.info(f"!{client_socket.getpeername()} disconnected")
            selector.unregister(client_socket)
            client_socket.close()
    except:
        logging.error(f"Error with {client_socket.getpeername()}, closing socket")
        selector.unregister(client_socket)
        client_socket.close()

def common_data_handler(proto: Protocol, client_socket, data, address):
    """
    proto: Protocol enum (Protocol.TCP, Protocol.UDP, Protocol.TLS)
    sock: socket object (for TCP/TLS) or udp_socket (for UDP)
    data: bytes received
    addr: (ip, port) tuple
    """
    logging.info(f"<< {proto.value} << {address}: {data.decode()}")

    if proto == Protocol.UDP:
        client_socket.sendto(data, address)
    else:
        client_socket.sendall(data)
    logging.info(f">> {proto.value} >> {address}: {data.decode()}")


def tcp_udp_server(server_config):

    host = server_config["host"]
    tcp_port = int(server_config["tcp_port"])
    udp_port = int(server_config["udp_port"])
    tls_port = int(server_config["tls_port"])
    tls_cert_path = os.path.join(server_config["cert_dir"], server_config["cert_file"])
    tls_key_path = os.path.join(server_config["cert_dir"], server_config["key_file"])

    max_connections = int(server_config["max_connections"])
    max_payload_size = int(server_config["max_payload"])

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