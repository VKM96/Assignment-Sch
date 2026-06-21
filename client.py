import socket
import logging
import cmd
import ssl
import os
import jwt
import time
from client_config import client_config

DEFAULT_CLIENT_ID = "client0001"
CLIENT_AUTH_TOKEN_PREFIX = "AUTH "
SERVER_AUTH_OK_RESPONSE = "OK: AUTH_SUCCESS"

LOG_CLIENT_OUT_UDP = ">> UDP >> "
LOG_CLIENT_IN_UDP = "<< UDP >>"
LOG_CLIENT_OUT_TCP = ">> TCP >>"
LOG_CLIENT_IN_TCP = "<< TCP <<"
LOG_CLIENT_OUT_TLS = ">> TLS >>"
LOG_CLIENT_IN_TLS = "<< TLS <<"


def generate_jwt_token(client_id: str) -> str:
    "Generate a JWT token for the given client ID." 

    jwt_secret = client_config["jwt_secret"]
    jwt_algorithm = client_config["jwt_algorithm"]
    jwt_expiration = int(client_config["jwt_expiration"])

    payload = {
        "client_id": client_id,
        "exp": int(time.time()) + jwt_expiration
    }
    return jwt.encode(payload, jwt_secret, algorithm=jwt_algorithm)

def tcp_create_socket(host, port):
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect((host, port))
    logging.info(f"Connected to TCP server at {host}:{port}")
    return tcp_socket

def tcp_send(tcp_socket, message):
    tcp_socket.sendall(message.encode())
    logging.info(f"{LOG_CLIENT_OUT_TCP}{message}")
    data = tcp_socket.recv(1024)
    logging.info(f"{LOG_CLIENT_IN_TCP}{data.decode()}")

def tcp_close(tcp_socket):
    tcp_socket.close()
    logging.info("TCP socket closed.")

def tls_create_socket(host, port, cert_path, client_id):
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=cert_path)  # Load server certificate for verification
    context.verify_mode = ssl.CERT_REQUIRED  # Require server certificate verification
    try:
        tcp_raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tls_socket= context.wrap_socket(tcp_raw_socket, server_hostname=host)
        tls_socket.connect((host, port))
        logging.info(f"Connected to TLS TCP server at {host}:{port}")

        # send auth token generated from client_id as a part of Authentication
        token = generate_jwt_token(client_id)
        auth_message = f"{CLIENT_AUTH_TOKEN_PREFIX}{token}"
        tls_socket.sendall(auth_message.encode())
        logging.info(f"{LOG_CLIENT_OUT_TLS}{auth_message}")

        server_response = tls_socket.recv(32).decode().strip()
        logging.info(f"{LOG_CLIENT_IN_TLS}{server_response}")

        if server_response != SERVER_AUTH_OK_RESPONSE:
            logging.error(f"Authentication failed with {host}:{port}: {server_response}")
            tls_socket.close()
            return None
        
        return tls_socket
    
    except ssl.SSLError as e:
        logging.error(f"TLS handshake failed with {host}:{port}: {e}")
        return None
    
    except Exception as e:
        logging.error(f"Connection error with TLS TCP server at {host}:{port}: {e}")
        return None

def tls_send(tls_socket, message):
    tls_socket.sendall(message.encode())
    logging.info(f"{LOG_CLIENT_OUT_TLS}{message}")
    data = tls_socket.recv(1024)
    logging.info(f"{LOG_CLIENT_IN_TLS} {data.decode()}")

def tls_close(tls_socket):
    tls_socket.close()
    logging.info("TLS socket closed.")


def udp_send(host, port, message):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.sendto(message.encode(), (host, port))
    logging.info(f"{LOG_CLIENT_OUT_UDP}{message}")
    data, _ = udp_socket.recvfrom(1024)
    logging.info(f"{LOG_CLIENT_IN_UDP} {data.decode()}")
    udp_socket.close()
class ClientCLI(cmd.Cmd):
    intro = "Welcome to the TCP/UDP client. Type help to list commands.\n"
    prompt = "client> "

    def __init__(self):
        super().__init__()
        self.host = client_config["host"]
        self.tcp_port = int(client_config["tcp_port"])
        self.udp_port = int(client_config["udp_port"])
        self.tls_port = int(client_config["tls_port"])
        self.cert_path = os.path.join(client_config["cert_dir"], client_config["cert_file"])

        self.tcp_socket = None
        self.udp_socket = None
        self.tls_socket = None
        os.makedirs(client_config["cert_dir"], exist_ok=True)

        self.client_id = DEFAULT_CLIENT_ID

    def do_set_client_id(self, arg):
        "Set the client ID: set_client_id <client_id>"
        if not arg:
            logging.warning(f"No client ID provided, using default {DEFAULT_CLIENT_ID}.")
            return
        self.client_id = arg
        logging.info(f"Client ID set to: {self.client_id}")

    def do_tcp_connect(self, arg):
        "Connect to TCP server: tcp_connect"
        if self.tcp_socket:
            logging.warning("Already connected to TCP server.")
            return
        self.tcp_socket = tcp_create_socket(self.host, self.tcp_port)

    def do_tcp_send(self, arg):
        "Send message to TCP server: tcp_send <message>"
        if not self.tcp_socket:
            logging.warning("Not connected to TCP server.")
            return
        if not arg.strip():
            logging.warning("No message provided to send.")
            return
        tcp_send(self.tcp_socket, arg)

    def do_tcp_disconnect(self, arg):
        "Disconnect from TCP server: tcp_disconnect"
        if self.tcp_socket:
            tcp_close(self.tcp_socket)
            self.tcp_socket = None
        else:
            logging.warning("Not connected to TCP server.")

    def do_tls_connect(self, arg):
        "Connect to TLS TCP server: tls_connect"
        if self.tls_socket:
            logging.warning("Already connected to TLS TCP server.")
            return
        self.tls_socket = tls_create_socket(self.host, self.tls_port, self.cert_path, self.client_id)

    def do_tls_send(self, arg):
        "Send message to TLS TCP server: tls_send <message>"
        if not self.tls_socket:
            logging.warning("Not connected to TLS TCP server.")
            return
        if not arg.strip():
            logging.warning("No message provided to send.")
            return
        tls_send(self.tls_socket, arg)

    def do_tls_disconnect(self, arg):
        "Disconnect from TLS TCP server: tls_disconnect"
        if self.tls_socket:
            tls_close(self.tls_socket)
            self.tls_socket = None
        else:
            logging.warning("Not connected to TLS TCP server.")

    def do_udp_send(self, arg):
        "Send message to UDP server: udp_send <message>"
        if not arg:
            logging.warning("No message provided to send.")
            return
        udp_send(self.host, self.udp_port, arg)

    def do_client_info(self, arg):
        "Display client information: client_info"
        logging.info(f"Client ID: {self.client_id}")
        logging.info(f"Host: {self.host}")
        logging.info(f"TCP Port: {self.tcp_port}")
        logging.info(f"UDP Port: {self.udp_port}")
        logging.info(f"TLS Port: {self.tls_port}")

    def do_quit(self, arg):
        "Exit the client: quit"
        if self.tcp_socket:
            tcp_close(self.tcp_socket)
        if self.udp_socket:
            self.udp_socket.close()
        if self.tls_socket:
            tls_close(self.tls_socket)
        logging.info("Exiting client.")
        return True

if __name__ == "__main__":
    ClientCLI().cmdloop()