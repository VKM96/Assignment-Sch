"""
server_config.py - configuration parameters for TCP/UDP Echo Server

This module implements handles all the configurable params for server.py

Key components:
- env variables are parsed though dotenv 
- All env variables also have a default fallback 


Usage:
- Import this module in server.py 

Dependencies:
- .env file 

TODO:

"""

"""
------------------------------------------------------------
IMPORTS
------------------------------------------------------------
"""

import os
import logging
from dotenv import load_dotenv

"""
------------------------------------------------------------
DEFAULTS
------------------------------------------------------------
"""

SERVER_VERSION = "1.0.0"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_HOST_TCP_PORT = 65432
DEFAULT_HOST_UDP_PORT = 65433
DEFAULT_HOST_TLS_PORT = 65434
DEFAULT_MAX_NUM_CONNECTIONS = 5

DEFAULT_CERT_DIR = "certs"
DEFAULT_CERT_FILE = "server.crt"
DEFAULT_KEY_FILE = "server.key"

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "server.log"

DEFAULT_JWT_SECRET = "JWT_SECRET_KEY_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_JWT_EXPIRATION = 3600  # 1 hour

DEFAULT_MAX_PAYLOAD = 4096 # 4KB size limit

DEFAULT_RATE_LIMIT_MAX_MESSAGES = 5
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 10

"""
------------------------------------------------------------
CONFIGURATION SETUP
------------------------------------------------------------
"""

# Load environment variables from .env file
env_loaded = load_dotenv()

server_config = {
    "host": os.getenv("ENV_HOST", DEFAULT_HOST),
    "tcp_port": os.getenv("ENV_HOST_TCP_PORT", DEFAULT_HOST_TCP_PORT),
    "udp_port": os.getenv("ENV_HOST_UDP_PORT", DEFAULT_HOST_UDP_PORT),
    "tls_port": os.getenv("ENV_HOST_TLS_PORT", DEFAULT_HOST_TLS_PORT),
    "max_connections": os.getenv("ENV_MAX_NUM_CONNECTIONS", DEFAULT_MAX_NUM_CONNECTIONS),
    "cert_dir": os.getenv("ENV_CERT_DIR", DEFAULT_CERT_DIR),
    "cert_file": os.getenv("ENV_CERT_FILE", DEFAULT_CERT_FILE),
    "key_file": os.getenv("ENV_KEY_FILE", DEFAULT_KEY_FILE),
    "log_dir": os.getenv("ENV_LOG_DIR", DEFAULT_LOG_DIR),
    "log_file": os.getenv("ENV_SERVER_LOG_FILE", DEFAULT_LOG_FILE),
    "jwt_secret": os.getenv("ENV_JWT_SECRET", DEFAULT_JWT_SECRET),
    "jwt_algorithm": os.getenv("ENV_JWT_ALGORITHM", DEFAULT_JWT_ALGORITHM),
    "jwt_expiration": os.getenv("ENV_JWT_EXPIRATION", DEFAULT_JWT_EXPIRATION),
    "max_payload" : os.getenv("ENV_MAX_PAYLOAD", DEFAULT_MAX_PAYLOAD),
    "rate_limit_max_messages": int(os.getenv("ENV_RATE_LIMIT_MAX_MESSAGES", DEFAULT_RATE_LIMIT_MAX_MESSAGES)),
    "rate_limit_window_seconds": int(os.getenv("ENV_RATE_LIMIT_WINDOW_SECONDS", DEFAULT_RATE_LIMIT_WINDOW_SECONDS))
}

# create log directory if it does not exist 
os.makedirs(server_config["log_dir"], exist_ok=True)
log_file_path = os.path.join(server_config["log_dir"], server_config["log_file"])

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()]
                    )

if env_loaded:
    logging.info(".env file loaded successfully.")
else:
    logging.warning("No .env file found. Using defaults.")

for key, value in server_config.items():
    logging.debug(f"{key}: {value}")
