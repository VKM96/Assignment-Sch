#!/bin/bash
set -e

APP_DIR="/opt/myapp"
LOG_DIR="/var/log/myapp"
VENV_DIR="$APP_DIR/.venv"

function init_setup() {
    echo ">>> Initializing MyApp environment..."

    # 1. Create log directory with secure permissions
    sudo mkdir -p "$LOG_DIR"
    sudo chown $USER:$USER "$LOG_DIR"
    sudo chmod 600 "$LOG_DIR"

    # 2. Create virtual environment if missing
    if [ ! -d "$VENV_DIR" ]; then
        echo ">>> Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi

    # 3. Activate venv and install dependencies
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r "$APP_DIR/requirements.txt"

    echo ">>> Init setup complete."
}

function launcher_menu() {
    source "$VENV_DIR/bin/activate"
    while true; do
        echo "-----------------------------------"
        echo " MyApp Launcher Menu"
        echo "-----------------------------------"
        echo "1) Run TCP/UDP Server"
        echo "2) Run Client"
        echo "3) Generate Certificates"
        echo "4) Exit"
        echo "-----------------------------------"
        read -rp "Choose an option: " choice

        case $choice in
            1) "$VENV_DIR/bin/python" -m src_server.server ;;
            2) "$VENV_DIR/bin/python" -m src_client.client ;;
            3) "$VENV_DIR/bin/python" certs/gen_cert.py ;;
            4) echo "Exiting..."; break ;;
            *) echo "Invalid choice" ;;
        esac
    done
}

# Mode selection
case "$1" in
    --init) init_setup ;;
    --menu) launcher_menu ;;
    *)
        echo "Usage: $0 [--init | --menu]"
        exit 1
        ;;
esac
