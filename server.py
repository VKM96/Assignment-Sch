"""
server.py - TCP/UDP Echo Server

This module implements a simple tcp, udp echo server

Key features:
- Event-driven architecture using selectors
- TLS authentication via JWT tokens 
- Logging to console and log files
- env variables for server configuration see server_config.py 
- All data handling is funneled though common_data_handler after respective connection handlers

Usage:
- >>> python server.py 
- run_server.bat can also be used    

Dependencies:
- server_config.py for default settings.
- SSL certificates for TLS support.

TODO:
- shutdown strategy needs further refinement 
- rate limiting is not yet implemented 
- Unit tests need to be added 
- Logs do not manage sensitive data differently 

"""

"""
------------------------------------------------------------
IMPORTS
------------------------------------------------------------
"""

import selectors
import socket
import logging
import ssl
import os
import jwt
from enum import Enum
from server_config import server_config 
from server_config import SERVER_VERSION

"""
------------------------------------------------------------
GLOBAL HELPERS
------------------------------------------------------------
"""

CLIENT_AUTH_TOKEN_PREFIX = "AUTH "      # Prefix for client Auth messages 
SERVER_AUTH_OK_RESPONSE = "OK: AUTH_SUCCESS" # Server Auth response 
SERVER_ERROR_RESPONSE = "SERVER: ERROR" # Server error response 
SERVER_NW_BUF_SIZE = 65535 # Server network buffer size 


class Protocol(Enum):
    """
    Enumeration of supported network protocols.

    Members:
        TCP (str): TCP
        UDP (str): UDP
        TLS (str): TCP over TLS
    """
    TCP = "TCP"
    UDP = "UDP"
    TLS = "TLS"

# Global selector used to multiplex I/O events across TCP, UDP, and TLS sockets
selector = selectors.DefaultSelector()

"""
------------------------------------------------------------
HELPER FUNCTIONS
------------------------------------------------------------
"""

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
    """
    Validate incoming payload size and encoding.
    Returns (success, decoded_data, error_reason).
    """
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
    """Safely close sockets without crashing.

    Unregisters the socket from the selector and closes it if not closed already
    """
    try:
        selector.unregister(client_socket)
    except Exception:
        pass
    try:
        client_socket.close()
    except Exception:
        pass
    logging.info(f"Closed {proto.value} connection with {address}")


def stream_data_handler(client_socket, proto: Protocol, address):
    """
    Handle incoming data for stream-based protocols (TCP/TLS).

    Args:
        client_socket: The socket object for the client connection.
        proto (Protocol): Protocol type (TCP or TLS).
        address (tuple): Client address (IP, port).
    """

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
    Handle incoming data for TCP, UDP, or TLS connections.

    Args:
        proto (Protocol): Protocol type (TCP, UDP, TLS).
        client_socket: Socket object (stream or datagram).
        data (bytes): Raw data received from client.
        address (tuple): Client (ip, port).
    """
    #todo Rate-limit check should go here
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

"""
------------------------------------------------------------
TCP
------------------------------------------------------------
"""

def tcp_server_start(host, port, max_connections):
    """
    Initialize and start a TCP server.

    Args:
        host (str): IP address to bind the server.
        port (int): Port number for TCP connections.
        max_connections (int): Maximum number of simultaneous clients.

    Returns:
        socket: The listening TCP socket.
    """
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind((host, port))
    tcp_socket.listen(max_connections)
    tcp_socket.setblocking(False)

    selector.register(tcp_socket, selectors.EVENT_READ, tcp_connection_handler)
    logging.info(f"TCP Server listening on {host}:{port}")
    return tcp_socket

def tcp_connection_handler(tcp_socket):
    """
    Accept a new TCP client connection and register it with the selector.

    Args:
        tcp_socket: The listening TCP socket.
    """
    connection, address = tcp_socket.accept()
    connection.setblocking(False)

    selector.register(connection, selectors.EVENT_READ, lambda sock: stream_data_handler(sock, Protocol.TCP, address))
    logging.info(f"TCP Connection from {address}")

"""
------------------------------------------------------------
TLS
------------------------------------------------------------
"""

def tls_server_start(host, port, max_connections, tls_cert_path, tls_key_path):
    """
    Initialize and start a TLS-secured server.

    Args:
        host (str): IP address to bind the server.
        port (int): Port number for TLS connections.
        max_connections (int): Maximum number of simultaneous clients.
        tls_cert_path (str): Path to TLS certificate file.
        tls_key_path (str): Path to TLS private key file.

    Returns:
        socket: The listening TLS socket.
    """
    tls_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tls_socket.bind((host, port))
    tls_socket.listen(max_connections)
    tls_socket.setblocking(False) # Non-blocking mode for selector

   # Configure TLS context with certificate and key
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    os.makedirs(server_config["cert_dir"], exist_ok=True)
    context.load_cert_chain(certfile=tls_cert_path, keyfile=tls_key_path)

    # wrap the TCP socket with SSL context and register it with the selector
    selector.register(tls_socket, selectors.EVENT_READ, lambda sock: tls_connection_handler(sock, context))
    logging.info(f"TLS Server listening on {host}:{port}")
    return tls_socket

def tls_connection_handler(tcp_socket, context):
    """
    Accept and authenticate a new TLS client connection.

    Args:
        tcp_socket: The listening TLS socket.
        context: SSL context configured with server cert/key.
    """
    connection, address = tcp_socket.accept()
    try:
        # Perform TLS handshake
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
        
        # Send success response and register for data handling
        logging.info(f"TLS>> {SERVER_AUTH_OK_RESPONSE}")
        connection.sendall(SERVER_AUTH_OK_RESPONSE.encode())
        connection.setblocking(False)
        selector.register(connection, selectors.EVENT_READ, lambda sock: stream_data_handler(sock, Protocol.TLS, address))

    except ssl.SSLError as e:
        logging.error(f"TLS handshake failed with {address}: {e}")
        socket_close(connection, Protocol.TLS, address)

"""
------------------------------------------------------------
UDP
------------------------------------------------------------
"""

def udp_server_start(host, port):
    """
    Initialize and start a UDP server.

    Args:
        host (str): IP address to bind the server.
        port (int): Port number for UDP connections.

    Returns:
        socket: The listening UDP socket.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((host, port))
    udp_socket.setblocking(False)
    selector.register(udp_socket, selectors.EVENT_READ, udp_connection_handler)
    logging.info(f"UDP Server listening on {host}:{port}")
    return udp_socket

def udp_connection_handler(udp_socket):
    """
    Handle incoming UDP datagrams.

    Args:
        udp_socket: The bound UDP socket.
    """
    try:
        data, address = udp_socket.recvfrom(SERVER_NW_BUF_SIZE)
        common_data_handler(Protocol.UDP, udp_socket, data, address)
    except Exception as e:
        socket_close(udp_socket, Protocol.UDP, "<unknown>")


"""
------------------------------------------------------------
CORE IMPLEMENTATION
------------------------------------------------------------
"""

def tcp_udp_server(server_config):
    """
    Start TCP, UDP, and TLS servers and run the main selector loop.

    Args:
        server_config (dict): Configuration dictionary with host, ports,
                              cert paths, and connection limits.
    """
    # Extract configuration values
    host = server_config["host"]
    tcp_port = int(server_config["tcp_port"])
    udp_port = int(server_config["udp_port"])
    tls_port = int(server_config["tls_port"])
    tls_cert_path = os.path.join(server_config["cert_dir"], server_config["cert_file"])
    tls_key_path = os.path.join(server_config["cert_dir"], server_config["key_file"])
    max_connections = int(server_config["max_connections"])

    # Initialize servers for each protocol
    tcp_server_start(host, tcp_port, max_connections)     # TCP Socket    
    udp_server_start(host, udp_port)     # UDP Socket
    tls_server_start(host, tls_port, max_connections, tls_cert_path, tls_key_path)  # TLS Socket

    logging.info(f"Starting Server v{SERVER_VERSION}, waiting for connections. Press CTRL+C to stop")

    try:
        # Main event loop: wait for socket events and dispatch handlers
        while True:
            events = selector.select(timeout=1) 
            for key, mask in events:
                callback = key.data
                callback(key.fileobj)   
    except KeyboardInterrupt:
        #TODO Better shutdown mechanism to be devised
        logging.info("Exit Signal received. Server is shutting down.")
    finally:
        # Cleanup selector and sockets
        selector.close()
        logging.info("All sockets closed.")

if __name__ == "__main__":
    tcp_udp_server(server_config)