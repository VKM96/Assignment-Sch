"""
server_authenticator.py - Authentication strategy abstraction for server

This module implements an authentication strategy pattern similar to
server_rate_limiter.py, allowing the server to swap authentication
mechanisms without modifying server logic.

Key components:
- Authenticator: Base class for authentication implementations
- JWTAuthenticator: JWT-based authentication implementation
- AuthenticatorService: Wrapper that delegates to a chosen authenticator

Usage:
    authenticator = AuthenticatorService(
        JWTAuthenticator(jwt_secret, jwt_algorithm)
    )
    success, client_id = authenticator.authenticate(token)
"""

from src_server.server_logging import get_logger
import jwt

logger = get_logger(__name__)


class AuthenticationError(Exception):
    """Exception raised when client authentication fails."""
    pass


class Authenticator:
    """Base class for authentication strategies."""

    def authenticate(self, token: str) -> tuple[bool, str | None]:
        """Authenticate a token and return (success, client_id)."""
        raise NotImplementedError("Subclasses must implement authenticate()")


class JWTAuthenticator(Authenticator):
    """JWT authentication implementation."""

    def __init__(self, jwt_secret: str, jwt_algorithm: str):
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm

    def authenticate(self, token: str) -> tuple[bool, str | None]:
        """Validate the JWT token and return (success, client_id)."""
        try:
            decoded_token = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            client_id = decoded_token.get("client_id", "unknown")
            return True, client_id
        except jwt.ExpiredSignatureError:
            logger.error("JWT token has expired.")
            return False, None
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token.")
            return False, None


