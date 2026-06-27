#!/bin/bash
#run_server.sh

# We are in project root
cd "$(dirname "$0")/.."
echo "Running from $(pwd)"

# Path to venv Python
PYTHON="./.venv/bin/python"

# Check if venv exists
if [ ! -x "$PYTHON"]; then
	echo "virtual env not found at $PYTHON"
	echo "Run: python3 -m venv .venv"
	exit 1
fi

echo "Starting client.py with $PYTHON"
exec "$PYTHON" -m src_server.server



