import socket
import logging
import cmd
import ssl
import os
from client_config import client_config


def tcp_create_socket(host, port):
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect((host, port))
    logging.info(f"Connected to TCP server at {host}:{port}")
    return tcp_socket

def tcp_send(tcp_socket, message):
    tcp_socket.sendall(message.encode())
    logging.info(f"Sent to TCP server: {message}")
    data = tcp_socket.recv(1024)
    logging.info(f"Received from TCP server: {data.decode()}")

def tcp_close(tcp_socket):
    tcp_socket.close()
    logging.info("TCP socket closed.")

def tls_create_socket(host, port, cert_path):
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=cert_path)  # Load server certificate for verification
    context.verify_mode = ssl.CERT_REQUIRED  # Require server certificate verification
    try:
        tcp_raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tls_socket= context.wrap_socket(tcp_raw_socket, server_hostname=host)
        tls_socket.connect((host, port))
        logging.info(f"Connected to TLS TCP server at {host}:{port}")
        return tls_socket
    except ssl.SSLError as e:
        logging.error(f"TLS handshake failed with {host}:{port}: {e}")
        return None
    except Exception as e:
        logging.error(f"Connection error with TLS TCP server at {host}:{port}: {e}")
        return None

def tls_send(tls_socket, message):
    tls_socket.sendall(message.encode())
    logging.info(f"Sent to TLS TCP server: {message}")
    data = tls_socket.recv(1024)
    logging.info(f"Received from TLS TCP server: {data.decode()}")

def tls_close(tls_socket):
    tls_socket.close()
    logging.info("TLS socket closed.")


def udp_send(host, port, message):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.sendto(message.encode(), (host, port))
    logging.info(f"Sent to UDP server: {message}")
    data, _ = udp_socket.recvfrom(1024)
    logging.info(f"Received from UDP server: {data.decode()}")
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
        self.tls_socket = tls_create_socket(self.host, self.tls_port, self.cert_path)

    def do_tls_send(self, arg):
        "Send message to TLS TCP server: tls_send <message>"
        if not self.tls_socket:
            logging.warning("Not connected to TLS TCP server.")
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

    def do_quit(self, arg):
        "Exit the client: quit"
        if self.tcp_socket:
            tcp_close(self.tcp_socket)
        if self.udp_socket:
            self.udp_socket.close()
        logging.info("Exiting client.")
        return True

if __name__ == "__main__":
    ClientCLI().cmdloop()