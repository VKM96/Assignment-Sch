import socket
import logging
import cmd

DEFAULT_HOST = "127.0.0.1"
DEFAULT_HOST_TCP_PORT = 65432
DEFAULT_HOST_UDP_PORT = 65433
LOG_FILE = "client.log"

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
        self.host = DEFAULT_HOST
        self.tcp_port = DEFAULT_HOST_TCP_PORT
        self.udp_port = DEFAULT_HOST_UDP_PORT
        self.tcp_socket = None
        self.udp_socket = None

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