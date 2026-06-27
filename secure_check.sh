#!/bin/bash
# secure_check.sh - Verify server health and security

# Load environment variables from src_server/.env
set -a
source src_server/.env
set +a

# Configuration from .env
SERVICE_NAME="myapp.service"
TCP_PORT=${ENV_HOST_TCP_PORT:-65432}
UDP_PORT=${ENV_HOST_UDP_PORT:-65433}
TLS_PORT=${ENV_HOST_TLS_PORT:-65434}
LOG_DIR=${ENV_LOG_DIR:-/var/log/myapp}
LOG_FILE=${ENV_LOG_FILE:-server.log}
CERT_DIR="${ENV_CERT_DIR:-certs}"
CERT_FILE=${ENV_CERT_FILE:-server.crt}
KEY_FILE=${ENV_KEY_FILE:-server.key}
CONFIG_FILE="src_server/.env"

# Expected permissions
PERM_CONFIG="600"
PERM_LOG="600"
PERM_CERT="644"
PERM_KEY="644"

echo "=== Secure Check Script ==="

# 1. Verify systemd service status
echo "[*] Checking service status..."
systemctl is-active --quiet $SERVICE_NAME
if [ $? -eq 0 ]; then
    echo "PASS: Service '$SERVICE_NAME' is running"
else
    echo "FAIL: Service '$SERVICE_NAME' is NOT running"
fi

# 2. Verify TCP port
echo "[*] Checking if TCP port $TCP_PORT is open..."
ss -ltn 2>/dev/null | grep -q ":$TCP_PORT" 
if [ $? -eq 0 ]; then
   echo "PASS: TCP port $TCP_PORT is open"
else
    echo "FAIL: TCP port $TCP_PORT is NOT open"
fi

# 3. Verify UDP port
echo "[*] Checking if UDP port $UDP_PORT is open..."
ss -lun 2>/dev/null | grep -q ":$UDP_PORT"
if [ $? -eq 0 ]; then
    echo "PASS: UDP port $UDP_PORT is open"
else
    echo "FAIL: UDP port $UDP_PORT is NOT open"
fi

# 4. Verify TLS port (treated as TCP)
echo "[*] Checking if TLS port $TLS_PORT is open..."
ss -ltn 2>/dev/null | grep -q ":$TLS_PORT"
if [ $? -eq 0 ]; then
    echo "PASS: TLS port $TLS_PORT is open"
else
    echo "FAIL: TLS port $TLS_PORT is NOT open"
fi

# 5. Verify file permissions
echo "[*] Checking file permissions..."
check_perms() {
    FILE=$1
    EXPECTED=$2
    if [ -f "$FILE" ]; then
        ACTUAL=$(stat -c "%a" "$FILE")
        if [ "$ACTUAL" = "$EXPECTED" ]; then
            echo "PASS: $FILE has correct permissions ($EXPECTED)"
        else
            echo "FAIL: $FILE has permissions $ACTUAL (expected $EXPECTED)"
        fi
    else
        echo "FAIL: $FILE not found"
    fi
}

check_perms "$CONFIG_FILE" "$PERM_CONFIG"
check_perms "$LOG_DIR/$LOG_FILE" "$PERM_LOG"
check_perms "$CERT_DIR/$CERT_FILE" "$PERM_CERT"
check_perms "$CERT_DIR/$KEY_FILE" "$PERM_KEY"

echo "=== Secure Check Complete ==="
