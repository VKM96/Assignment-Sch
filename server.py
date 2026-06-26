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
- Unit tests need to be added 
- Logs do not manage sensitive data differently 

"""

"""
------------------------------------------------------------
IMPORTS
------------------------------------------------------------
"""

import os
import selectors
import socket
import ssl
from enum import Enum
from functools import partial
from server_config import server_config 
from server_config import SERVER_VERSION
from server_rate_limiter import RateLimiter, FixedWindowCounter
from server_payload_validator import validate_payload
from server_authenticator import AuthenticatorService, JWTAuthenticator
from server_logging import configure_logging, get_logger

logger = get_logger(__name__)

"""
------------------------------------------------------------
GLOBAL HELPERS
------------------------------------------------------------
"""

CLIENT_AUTH_TOKEN_PREFIX = "AUTH "      # Prefix for client Auth messages 
SERVER_AUTH_OK_RESPONSE = "OK: AUTH_SUCCESS" # Server Auth response 
SERVER_ERROR_RESPONSE = "SERVER: ERROR" # Server error response 
SERVER_NW_BUF_SIZE = 65535 # Server network buffer size 
TLS_HANDSHAKE_TIMEOUT_SECONDS = 5


class Protocol(Enum):
    """  Enumeration of supported network protocols """
    TCP = "TCP"
    UDP = "UDP"
    TLS = "TLS"

class EchoServer:
    """Coordinate TCP, UDP, and TLS echo server behavior."""

    def __init__(self, config: dict) -> None:
        configure_logging(config)
        self.config = config
        self.selector = selectors.DefaultSelector()
        self.rate_limiter = RateLimiter(
            FixedWindowCounter(
                max_messages=int(self.config["rate_limit_max_messages"]),
                window_seconds=int(self.config["rate_limit_window_seconds"]),
            )
        )
        self.authenticator = AuthenticatorService(
            JWTAuthenticator(
                jwt_secret=self.config["jwt_secret"],
                jwt_algorithm=self.config["jwt_algorithm"],
            )
        )
        self._sockets = []

    def _close_socket(self, client_socket, proto: Protocol, address: str = "unknown") -> None:
        """Safely close a client socket and unregister it from the selector."""
        try:
            self.selector.unregister(client_socket)
        except Exception:
            pass
        try:
            client_socket.close()
        except Exception:
            pass
        logger.info(f"Closed {proto.value} connection with {address}")

    def _send_error(self, client_socket, proto: Protocol, message: str, address) -> None:
        """Send an error response for stream-based protocols and close the connection."""
        if proto == Protocol.UDP:
            return
        try:
            client_socket.sendall(f"{SERVER_ERROR_RESPONSE}: {message}\n".encode())
        except Exception:
            pass
        self._close_socket(client_socket, proto, address)

    def _handle_stream_data(self, client_socket, proto: Protocol, address) -> None:
        """Handle incoming data for TCP or TLS connections."""
        try:
            data = client_socket.recv(SERVER_NW_BUF_SIZE)
            if data:
                self._handle_message(proto, client_socket, data, address)
            else:
                logger.info(f"!{address} disconnected")
                self._close_socket(client_socket, proto, address)
        except Exception as exc:
            logger.error(f"{proto.value} error with {address}: {exc}")
            self._close_socket(client_socket, proto, address)

    def _handle_message(self, proto: Protocol, client_socket, data: bytes, address) -> None:
        """Validate, log, and echo incoming payloads."""
        client_key = f"{address[0]}:{address[1]}"

        if not self.rate_limiter.is_allowed(client_key):
            logger.warning(
                f"{proto.value} : {address} : Rate limit exceeded "
                f"(max {self.config['rate_limit_max_messages']} messages per "
                f"{self.config['rate_limit_window_seconds']} seconds)"
            )
            if proto != Protocol.UDP:
                self._send_error(client_socket, proto, "Rate limit exceeded", address)
            return

        is_valid_data, validated_data, reason = validate_payload(data, int(self.config["max_payload"]))
        if not is_valid_data:
            logger.warning(f"{proto.value} : {address} : {reason}")
            if proto != Protocol.UDP:
                self._send_error(client_socket, proto, reason, address)
            return

        logger.info(f"<< {proto.value} << {address}: {validated_data}")

        if proto == Protocol.UDP:
            client_socket.sendto(data, address)
        else:
            client_socket.sendall(data)

    def _setup_tcp_server(self, host: str, port: int, max_connections: int) -> socket.socket:
        """Create and register the TCP listening socket."""
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.bind((host, port))
        tcp_socket.listen(max_connections)
        tcp_socket.setblocking(False)

        self._sockets.append(tcp_socket)
        self.selector.register(
            tcp_socket,
            selectors.EVENT_READ,
            partial(self._handle_tcp_accept),
        )
        logger.info(f"TCP Server listening on {host}:{port}")
        return tcp_socket

    def _handle_tcp_accept(self, listening_socket) -> None:
        """Accept a new TCP connection and register it for reading."""
        connection, address = listening_socket.accept()
        connection.setblocking(False)
        self.selector.register(
            connection,
            selectors.EVENT_READ,
            partial(self._handle_stream_data, proto=Protocol.TCP, address=address),
        )
        logger.info(f"TCP Connection from {address}")

    def _setup_udp_server(self, host: str, port: int) -> socket.socket:
        """Create and register the UDP socket."""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind((host, port))
        udp_socket.setblocking(False)

        self._sockets.append(udp_socket)
        self.selector.register(
            udp_socket,
            selectors.EVENT_READ,
            partial(self._handle_udp_data),
        )
        logger.info(f"UDP Server listening on {host}:{port}")
        return udp_socket

    def _handle_udp_data(self, udp_socket) -> None:
        """Handle incoming UDP datagrams."""
        try:
            data, address = udp_socket.recvfrom(SERVER_NW_BUF_SIZE)
            self._handle_message(Protocol.UDP, udp_socket, data, address)
        except Exception as exc:
            logger.error(f"UDP error: {exc}")
            self._close_socket(udp_socket, Protocol.UDP, "<unknown>")

    def _setup_tls_server(self, host: str, port: int, max_connections: int, tls_cert_path: str, tls_key_path: str) -> socket.socket:
        """Create and register the TLS listening socket."""
        tls_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tls_socket.bind((host, port))
        tls_socket.listen(max_connections)
        tls_socket.setblocking(False)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        os.makedirs(self.config["cert_dir"], exist_ok=True)
        context.load_cert_chain(certfile=tls_cert_path, keyfile=tls_key_path)

        self._sockets.append(tls_socket)
        self.selector.register(
            tls_socket,
            selectors.EVENT_READ,
            partial(self._handle_tls_accept, context=context),
        )
        logger.info(f"TLS Server listening on {host}:{port}")
        return tls_socket

    def _handle_tls_accept(self, listening_socket, context) -> None:
        """Accept a TLS connection, authenticate it, and register it for data handling."""
        connection, address = listening_socket.accept()
        try:
            connection.settimeout(TLS_HANDSHAKE_TIMEOUT_SECONDS)
            connection = context.wrap_socket(connection, server_side=True)
            connection.settimeout(TLS_HANDSHAKE_TIMEOUT_SECONDS)
            logger.info(f"TLS Connection from {address}")

            try:
                auth_message = connection.recv(512).decode("utf-8").strip()
            except (socket.timeout, ConnectionResetError, ssl.SSLError, UnicodeDecodeError) as exc:
                logger.warning(f"TLS auth read failed with {address}: {exc}")
                self._close_socket(connection, Protocol.TLS, address)
                return

            logger.info(f"TLS<< {auth_message}")

            if not auth_message or not auth_message.startswith(CLIENT_AUTH_TOKEN_PREFIX):
                logger.error(f"Authentication failed with {address}: No AUTH message received")
                self._close_socket(connection, Protocol.TLS, address)
                return

            token = auth_message[len(CLIENT_AUTH_TOKEN_PREFIX) :].strip()
            is_success, client_id = self.authenticator.authenticate(token)
            if not is_success:
                logger.error(f"Authentication failed with {address}: Invalid JWT token")
                self._close_socket(connection, Protocol.TLS, address)
                return

            logger.info(f"TLS client {client_id} authenticated from {address}")
            logger.info(f"TLS>> {SERVER_AUTH_OK_RESPONSE}")
            connection.sendall(SERVER_AUTH_OK_RESPONSE.encode())
            connection.setblocking(False)
            self.selector.register(
                connection,
                selectors.EVENT_READ,
                partial(self._handle_stream_data, proto=Protocol.TLS, address=address),
            )
        except ssl.SSLError as exc:
            logger.error(f"TLS handshake failed with {address}: {exc}")
            self._close_socket(connection, Protocol.TLS, address)
        except (ConnectionResetError, BrokenPipeError, OSError) as exc:
            logger.warning(f"TLS connection interrupted with {address}: {exc}")
            self._close_socket(connection, Protocol.TLS, address)
        except Exception as exc:
            logger.error(f"TLS connection error with {address}: {exc}")
            self._close_socket(connection, Protocol.TLS, address)

    def start(self) -> None:
        """Initialize all listener sockets and run the main event loop."""
        host = self.config["host"]
        tcp_port = int(self.config["tcp_port"])
        udp_port = int(self.config["udp_port"])
        tls_port = int(self.config["tls_port"])
        tls_cert_path = os.path.join(self.config["cert_dir"], self.config["cert_file"])
        tls_key_path = os.path.join(self.config["cert_dir"], self.config["key_file"])
        max_connections = int(self.config["max_connections"])

        self._setup_tcp_server(host, tcp_port, max_connections)
        self._setup_udp_server(host, udp_port)
        self._setup_tls_server(host, tls_port, max_connections, tls_cert_path, tls_key_path)

        logger.info(f"Starting Server v{SERVER_VERSION}, waiting for connections. Press CTRL+C to stop")
        self.run()

    def run(self) -> None:
        """Run the main selector loop until interrupted."""
        try:
            while True:
                events = self.selector.select(timeout=1)
                for key, _ in events:
                    callback = key.data
                    callback(key.fileobj)
        except KeyboardInterrupt:
            logger.info("Exit Signal received. Server is shutting down.")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Close all registered sockets and the selector."""
        for sock in list(self._sockets):
            try:
                self.selector.unregister(sock)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
        self.selector.close()
        logger.info("All sockets closed.")


if __name__ == "__main__":
    EchoServer(server_config).start()