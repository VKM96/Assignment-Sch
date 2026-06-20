import os
import logging
from dotenv import load_dotenv

DEFAULT_HOST = "127.0.0.1"
DEFAULT_HOST_TCP_PORT = 65432
DEFAULT_HOST_UDP_PORT = 65433
DEFAULT_MAX_NUM_CONNECTIONS = 5
LOG_FILE = "server.log"

# Load environment variables from .env file
env_loaded = load_dotenv()

server_config = {
    "host": os.getenv("ENV_HOST", DEFAULT_HOST),
    "tcp_port": os.getenv("ENV_HOST_TCP_PORT", DEFAULT_HOST_TCP_PORT),
    "udp_port": os.getenv("ENV_HOST_UDP_PORT", DEFAULT_HOST_UDP_PORT),
    "max_connections": os.getenv("ENV_MAX_NUM_CONNECTIONS", DEFAULT_MAX_NUM_CONNECTIONS),
    "log_file": os.getenv("ENV_LOG_FILE", LOG_FILE),
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(server_config["log_file"]), logging.StreamHandler()]
                    )

# --- Runtime check ---
if env_loaded:
    logging.info(".env file loaded successfully.")
else:
    logging.warning("No .env file found. Using defaults only.")

for key, value in server_config.items():
    logging.debug(f"{key}: {value}")