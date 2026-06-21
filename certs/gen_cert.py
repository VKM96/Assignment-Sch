# certs/gen_cert.py
import os
import sys
import subprocess

def main():
    # Work inside the certs folder
    certs_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(certs_dir)

    openssl = "openssl"  # Adjust if OpenSSL is installed elsewhere

    config_file = os.path.join(certs_dir, "openssl.cnf")
    if not os.path.exists(config_file):
        print(f"Configuration file openssl.cnf not found in {certs_dir}")
        sys.exit(1)

    print("Generating server.crt and server.key...")
    result = subprocess.run([
        openssl, "req", "-new", "-x509", "-days", "365", "-nodes",
        "-out", os.path.join(certs_dir, "server.crt"),
        "-keyout", os.path.join(certs_dir, "server.key"),
        "-config", config_file
    ])

    if result.returncode != 0:
        print("OpenSSL command failed.")
        sys.exit(1)

    print("Certificate and key generated successfully.")
    print(f"Files created in {certs_dir}: server.crt, server.key")

if __name__ == "__main__":
    main()
