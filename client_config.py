import os
import logging
from dotenv import load_dotenv

CLIENT_VERSION = "1.0.0"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_HOST_TCP_PORT = 65432
DEFAULT_HOST_UDP_PORT = 65433
DEFAULT_HOST_TLS_PORT = 65434

DEFAULT_CERT_DIR = "certs"
DEFAULT_CERT_FILE = "server.crt"

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "client.log"

DEFAULT_JWT_SECRET = "JWT_SECRET_KEY_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_JWT_EXPIRATION = 3600  # 1 hour

# Load environment variables from .env file
env_loaded = load_dotenv()

client_config = {
    "host": os.getenv("ENV_HOST", DEFAULT_HOST),
    "tcp_port": os.getenv("ENV_HOST_TCP_PORT", DEFAULT_HOST_TCP_PORT),
    "udp_port": os.getenv("ENV_HOST_UDP_PORT", DEFAULT_HOST_UDP_PORT),
    "tls_port": os.getenv("ENV_HOST_TLS_PORT", DEFAULT_HOST_TLS_PORT),
    "cert_dir": os.getenv("ENV_CERT_DIR", DEFAULT_CERT_DIR),
    "cert_file": os.getenv("ENV_CERT_FILE", DEFAULT_CERT_FILE),
    "log_dir": os.getenv("ENV_LOG_DIR", DEFAULT_LOG_DIR),
    "log_file": os.getenv("ENV_LOG_FILE", DEFAULT_LOG_FILE),
    "jwt_secret": os.getenv("ENV_JWT_SECRET", DEFAULT_JWT_SECRET),
    "jwt_algorithm": os.getenv("ENV_JWT_ALGORITHM", DEFAULT_JWT_ALGORITHM),
    "jwt_expiration": int(os.getenv("ENV_JWT_EXPIRATION", DEFAULT_JWT_EXPIRATION))
}

os.makedirs(client_config["log_dir"], exist_ok=True)
log_file_path = os.path.join(client_config["log_dir"], client_config["log_file"])

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(log_file_path), logging.StreamHandler()]
                    )

# --- Runtime check ---
if env_loaded:
    logging.info(".env file loaded successfully.")
else:
    logging.warning("No .env file found. Using defaults only.")

for key, value in client_config.items():
    logging.debug(f"{key}: {value}")