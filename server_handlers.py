"""
server_handlers.py - Protocol-specific connection handlers for TCP, UDP, and TLS.

This module encapsulates the lower-level socket management, reading/writing,
and non-blocking TLS handshakes and authentication.
"""

import os
import selectors
import socket
import ssl
from enum import Enum
from functools import partial
from server_logging import get_logger
from server_payload_validator import validate_payload, PayloadValidationError
from server_rate_limiter import RateLimitExceededError

logger = get_logger(__name__)

CLIENT_AUTH_TOKEN_PREFIX = "AUTH "      # Prefix for client Auth messages 
SERVER_AUTH_OK_RESPONSE = "OK: AUTH_SUCCESS" # Server Auth response 
SERVER_ERROR_RESPONSE = "SERVER: ERROR" # Server error response 
SERVER_NW_BUF_SIZE = 65535 # Server network buffer size 


class Protocol(Enum):
    """Enumeration of supported network protocols"""
    TCP = "TCP"
    UDP = "UDP"
    TLS = "TLS"


class BaseProtocolHandler:
    """Abstract base class for all protocol-specific server handlers."""

    def __init__(self, server) -> None:
        self.server = server
        self.sockets = []

    def setup_server(self) -> None:
        """Create bind, listen on socket, and register with selector."""
        raise NotImplementedError("Subclasses must implement setup_server()")

    def _register_or_modify(self, sock: socket.socket, events: int, callback) -> None:
        """Safely register or modify a socket registration in the selector."""
        try:
            self.server.selector.modify(sock, events, callback)
        except KeyError:
            self.server.selector.register(sock, events, callback)

    def _close_client(self, client_socket: socket.socket, proto: Protocol, address: str = "unknown") -> None:
        """Safely close a client socket and unregister it from the selector."""
        try:
            self.server.selector.unregister(client_socket)
        except (KeyError, ValueError):
            pass
        try:
            client_socket.close()
        except OSError:
            pass
        logger.info(f"Closed {proto.value} connection with {address}")

    def _send_error(self, client_socket: socket.socket, proto: Protocol, message: str, address) -> None:
        """Send an error response to a stream client and close the connection."""
        if proto == Protocol.UDP:
            return
        try:
            client_socket.sendall(f"{SERVER_ERROR_RESPONSE}: {message}\n".encode())
        except OSError:
            pass
        self._close_client(client_socket, proto, address)

    def close(self) -> None:
        """Unregister and close all listening sockets managed by this handler."""
        for sock in list(self.sockets):
            try:
                self.server.selector.unregister(sock)
            except (KeyError, ValueError):
                pass
            try:
                sock.close()
            except OSError:
                pass
        self.sockets.clear()


class TCPHandler(BaseProtocolHandler):
    """Handler for TCP listening socket and stream connections."""

    def setup_server(self) -> None:
        host = self.server.config["host"]
        port = self.server.config["tcp_port"]
        max_connections = self.server.config["max_connections"]

        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_socket.bind((host, port))
        tcp_socket.listen(max_connections)
        tcp_socket.setblocking(False)

        self.sockets.append(tcp_socket)
        self.server.selector.register(
            tcp_socket,
            selectors.EVENT_READ,
            self._handle_accept,
        )
        logger.info(f"TCP Server listening on {host}:{port}")

    def _handle_accept(self, listening_socket: socket.socket) -> None:
        try:
            connection, address = listening_socket.accept()
            connection.setblocking(False)
            self._register_or_modify(
                connection,
                selectors.EVENT_READ,
                partial(self._handle_read, address=address),
            )
            logger.info(f"TCP Connection from {address}")
        except OSError as exc:
            logger.error(f"TCP accept failed: {exc}")

    def _handle_read(self, client_socket: socket.socket, address) -> None:
        try:
            data = client_socket.recv(SERVER_NW_BUF_SIZE)
            if data:
                try:
                    self.server.process_message(Protocol.TCP, client_socket, data, address)
                except (RateLimitExceededError, PayloadValidationError) as exc:
                    logger.warning(f"TCP : {address} : {exc}")
                    self._send_error(client_socket, Protocol.TCP, str(exc), address)
            else:
                logger.info(f"!{address} disconnected")
                self._close_client(client_socket, Protocol.TCP, address)
        except OSError as exc:
            logger.error(f"TCP error with {address}: {exc}")
            self._close_client(client_socket, Protocol.TCP, address)


class UDPHandler(BaseProtocolHandler):
    """Handler for connectionless UDP socket datagrams."""

    def setup_server(self) -> None:
        host = self.server.config["host"]
        port = self.server.config["udp_port"]

        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind((host, port))
        udp_socket.setblocking(False)

        self.sockets.append(udp_socket)
        self.server.selector.register(
            udp_socket,
            selectors.EVENT_READ,
            self._handle_read,
        )
        logger.info(f"UDP Server listening on {host}:{port}")

    def _handle_read(self, udp_socket: socket.socket) -> None:
        try:
            data, address = udp_socket.recvfrom(SERVER_NW_BUF_SIZE)
            try:
                self.server.process_message(Protocol.UDP, udp_socket, data, address)
            except (RateLimitExceededError, PayloadValidationError) as exc:
                logger.warning(f"UDP : {address} : {exc}")
        except OSError as exc:
            logger.error(f"UDP error: {exc}")


class TLSHandler(BaseProtocolHandler):
    """Handler for secure TLS connections with non-blocking handshake & JWT auth."""

    def setup_server(self) -> None:
        host = self.server.config["host"]
        port = self.server.config["tls_port"]
        max_connections = self.server.config["max_connections"]
        tls_cert_path = os.path.join(self.server.config["cert_dir"], self.server.config["cert_file"])
        tls_key_path = os.path.join(self.server.config["cert_dir"], self.server.config["key_file"])

        tls_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tls_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tls_socket.bind((host, port))
        tls_socket.listen(max_connections)
        tls_socket.setblocking(False)

        # Use secure default server context
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        os.makedirs(self.server.config["cert_dir"], exist_ok=True)
        self.context.load_cert_chain(certfile=tls_cert_path, keyfile=tls_key_path)

        self.sockets.append(tls_socket)
        self.server.selector.register(
            tls_socket,
            selectors.EVENT_READ,
            self._handle_accept,
        )
        logger.info(f"TLS Server listening on {host}:{port}")

    def _handle_accept(self, listening_socket: socket.socket) -> None:
        try:
            connection, address = listening_socket.accept()
            connection.setblocking(False)
            try:
                # Wrap socket without executing synchronous handshake
                tls_socket = self.context.wrap_socket(
                    connection,
                    server_side=True,
                    do_handshake_on_connect=False
                )
                self._register_or_modify(
                    tls_socket,
                    selectors.EVENT_READ,
                    partial(self._handle_handshake, address=address)
                )
                logger.info(f"TLS connection initiated from {address}")
            except ssl.SSLError as exc:
                logger.error(f"TLS wrap failed with {address}: {exc}")
                connection.close()
        except OSError as exc:
            logger.error(f"TLS accept failed: {exc}")

    def _handle_handshake(self, tls_socket: socket.socket, address) -> None:
        try:
            tls_socket.do_handshake()
            # Handshake complete! Modify registration to read JWT auth token
            self._register_or_modify(
                tls_socket,
                selectors.EVENT_READ,
                partial(self._handle_auth, address=address)
            )
        except ssl.SSLWantReadError:
            self._register_or_modify(
                tls_socket,
                selectors.EVENT_READ,
                partial(self._handle_handshake, address=address)
            )
        except ssl.SSLWantWriteError:
            self._register_or_modify(
                tls_socket,
                selectors.EVENT_WRITE,
                partial(self._handle_handshake, address=address)
            )
        except (ssl.SSLError, OSError) as exc:
            logger.error(f"TLS handshake failed with {address}: {exc}")
            self._close_client(tls_socket, Protocol.TLS, address)

    def _handle_auth(self, tls_socket: socket.socket, address) -> None:
        try:
            data = tls_socket.recv(512)
            if not data:
                logger.warning(f"TLS auth read failed with {address}: Client disconnected")
                self._close_client(tls_socket, Protocol.TLS, address)
                return

            auth_message = data.decode("utf-8").strip()
            logger.info(f"TLS<< {auth_message}")

            if not auth_message.startswith(CLIENT_AUTH_TOKEN_PREFIX):
                logger.error(f"Authentication failed with {address}: No AUTH message received")
                self._send_error(tls_socket, Protocol.TLS, "No AUTH message received", address)
                return

            token = auth_message[len(CLIENT_AUTH_TOKEN_PREFIX):].strip()
            is_success, client_id = self.server.authenticator.authenticate(token)
            if not is_success:
                logger.error(f"Authentication failed with {address}: Invalid JWT token")
                self._send_error(tls_socket, Protocol.TLS, "Invalid JWT token", address)
                return

            logger.info(f"TLS client {client_id} authenticated from {address}")
            logger.info(f"TLS>> {SERVER_AUTH_OK_RESPONSE}")
            tls_socket.sendall(SERVER_AUTH_OK_RESPONSE.encode())

            # Authentication successful! Modify registration to process standard message stream
            self._register_or_modify(
                tls_socket,
                selectors.EVENT_READ,
                partial(self._handle_client_data, address=address)
            )
        except ssl.SSLWantReadError:
            pass
        except ssl.SSLWantWriteError:
            self._register_or_modify(
                tls_socket,
                selectors.EVENT_WRITE,
                partial(self._handle_auth, address=address)
            )
        except (ssl.SSLError, OSError) as exc:
            logger.error(f"TLS authentication error with {address}: {exc}")
            self._close_client(tls_socket, Protocol.TLS, address)

    def _handle_client_data(self, tls_socket: socket.socket, address) -> None:
        try:
            data = tls_socket.recv(SERVER_NW_BUF_SIZE)
            if data:
                try:
                    self.server.process_message(Protocol.TLS, tls_socket, data, address)
                except (RateLimitExceededError, PayloadValidationError) as exc:
                    logger.warning(f"TLS : {address} : {exc}")
                    self._send_error(tls_socket, Protocol.TLS, str(exc), address)
            else:
                logger.info(f"!{address} disconnected")
                self._close_client(tls_socket, Protocol.TLS, address)
        except ssl.SSLWantReadError:
            pass
        except OSError as exc:
            logger.error(f"TLS client read error with {address}: {exc}")
            self._close_client(tls_socket, Protocol.TLS, address)
