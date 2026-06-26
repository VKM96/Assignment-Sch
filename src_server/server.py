"""
server.py - TCP/UDP Echo Server

This module implements a simple tcp, udp echo server.

Key features:
- Event-driven architecture using selectors
- TLS authentication via JWT tokens
- Logging to console and log files
- Configured via server_config.py
- Modular protocol handlers separating concerns

Usage:
- >>> python server.py
- run_server.bat can also be used
"""

import selectors
from src_server.server_config import server_config, SERVER_VERSION
from src_server.server_rate_limiter import FixedWindowCounter, RateLimitExceededError
from src_server.server_payload_validator import validate_payload, PayloadValidationError
from src_server.server_authenticator import JWTAuthenticator
from src_server.server_logging import configure_logging, get_logger
from src_server.server_handlers import Protocol, TCPHandler, UDPHandler, TLSHandler

logger = get_logger(__name__)

class EchoServer:
    """Coordinate TCP, UDP, and TLS echo server behavior using delegated handlers."""

    def __init__(self, config: dict) -> None:
        configure_logging(config)
        self.config = config
        self.selector = selectors.DefaultSelector()

        # Initialize rate limiter strategy directly
        self.rate_limiter = FixedWindowCounter(
            max_messages=self.config["rate_limit_max_messages"],
            window_seconds=self.config["rate_limit_window_seconds"],
        )

        # Initialize authenticator strategy directly
        self.authenticator = JWTAuthenticator(
            jwt_secret=self.config["jwt_secret"],
            jwt_algorithm=self.config["jwt_algorithm"],
        )

        # Instantiate protocol handlers
        self.handlers = [
            TCPHandler(self),
            UDPHandler(self),
            TLSHandler(self),
        ]

    def start(self) -> None:
        """Initialize all listener sockets and run the main event loop."""
        for handler in self.handlers:
            handler.setup_server()

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

    def process_message(self, proto: Protocol, client_socket, data: bytes, address) -> None:
        """Validate, log, and echo incoming payloads. Raises exceptions on failure."""
        client_key = f"{address[0]}:{address[1]}"

        # Enforce rate limiting
        if not self.rate_limiter.is_allowed(client_key):
            raise RateLimitExceededError(
                f"Rate limit exceeded (max {self.config['rate_limit_max_messages']} messages per "
                f"{self.config['rate_limit_window_seconds']} seconds)"
            )

        # Validate incoming data payload
        is_valid_data, validated_data, reason = validate_payload(data, self.config["max_payload"])
        if not is_valid_data:
            raise PayloadValidationError(reason or "Payload validation failed")

        logger.info(f"<< {proto.value} << {address}: {validated_data}")

        # Echo the raw data back to the client
        if proto == Protocol.UDP:
            client_socket.sendto(data, address)
        else:
            client_socket.sendall(data)

        logger.info(f">> {proto.value} >> {address}: {validated_data}")

    def shutdown(self) -> None:
        """Close all registered sockets and the selector."""
        for handler in self.handlers:
            handler.close()
        try:
            self.selector.close()
        except Exception:
            pass
        logger.info("All sockets closed.")


if __name__ == "__main__":
    EchoServer(server_config).start()