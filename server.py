from logging import config
from multiprocessing import context
import selectors
import socket
import logging
import ssl
from config  import server_config 

# Here is how certificates were signed for TLS:
# openssl req -new -x509 -days 365 -nodes -out server.crt -keyout server.key -config "openssl.cnf"

selector = selectors.DefaultSelector()

def tcp_server_start(host, port, max_connections):
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind((host, port))
    tcp_socket.listen(max_connections)
    tcp_socket.setblocking(False)

    selector.register(tcp_socket, selectors.EVENT_READ, tcp_connection_handler)
    logging.info(f"TCP Server listening on {host}:{port}")
    return tcp_socket

def tcp_server_tls_start(host, port, max_connections):
    tcp_socket_tls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket_tls.bind((host, port))
    tcp_socket_tls.listen(max_connections)
    tcp_socket_tls.setblocking(False)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    # wrap the TCP socket with SSL context and register it with the selector
    selector.register(tcp_socket_tls, selectors.EVENT_READ, lambda sock: tcp_connection_handler_tls(sock, context))
    logging.info(f"TCP Server listening on {host}:{port}")
    return tcp_socket_tls

def tcp_connection_handler(tcp_socket):
    connection, address = tcp_socket.accept()
    connection.setblocking(False)
    selector.register(connection, selectors.EVENT_READ, tcp_data_handler)
    logging.info(f"TCP Connection from {address}")

def tcp_connection_handler_tls(tcp_socket, context):
    connection, address = tcp_socket.accept()
    try:
        connection = context.wrap_socket(connection, server_side=True)
        connection.setblocking(False)
        selector.register(connection, selectors.EVENT_READ, tcp_data_handler)
        logging.info(f"TLS TCP Connection from {address}")
    except ssl.SSLError as e:
        logging.error(f"TLS handshake failed with {address}: {e}")
        connection.close()

def udp_server_start(host, port):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((host, port))
    udp_socket.setblocking(False)
    selector.register(udp_socket, selectors.EVENT_READ, udp_data_handler)
    logging.info(f"UDP Server listening on {host}:{port}")
    return udp_socket

def udp_data_handler(udp_socket):
    data, address = udp_socket.recvfrom(1024)
    logging.info(f"UDP -> {address}: {data.decode()}")
    udp_socket.sendto(data, address)

def tcp_data_handler(client_socket):
    try:
        data = client_socket.recv(1024)
        if data:
            logging.info(f"TCP -> {client_socket.getpeername()}: {data.decode()}")
            client_socket.sendall(data)
            logging.info(f"TCP <- {client_socket.getpeername()}")
        else:
            logging.info(f"!{client_socket.getpeername()} disconnected")
            selector.unregister(client_socket)
            client_socket.close()
    except:
        logging.error(f"TCP ! Error with {client_socket.getpeername()}, closing socket")
        selector.unregister(client_socket)
        client_socket.close()


def tcp_udp_server(server_config):

    host = server_config["host"]
    tcp_port = int(server_config["tcp_port"])  
    udp_port = int(server_config["udp_port"])
    tls_port = int(server_config["tls_port"])
    max_connections = int(server_config["max_connections"])

    tcp_server_start(host, tcp_port, max_connections)     # TCP Socket    
    udp_server_start(host, udp_port)     # UDP Socket
    tcp_server_tls_start(host, tls_port, max_connections)  # TLS Socket

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