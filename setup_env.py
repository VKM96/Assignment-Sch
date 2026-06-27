import os
import sys
import subprocess
import platform

def create_venv(project_root, venv_dir):
    if not os.path.exists(venv_dir):
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
    else:
        print("Virtual environment already exists.")

def install_requirements(python_path, project_root):
    req_file = os.path.join(project_root, "requirements.txt")
    if os.path.exists(req_file):
        print(f"Installing dependencies from {req_file}...")
        subprocess.check_call([python_path, "-m", "pip", "install", "-r", req_file])
    else:
        print("No requirements.txt found. Skipping dependency install.")

def spawn_process(script_path):
    system = platform.system()
    if system == "Windows":
        # Launch in a new Command Prompt window
        subprocess.Popen(["start", "cmd", "/k", script_path], shell=True)
    elif system == "Linux":
        # Launch in a new gnome-terminal window (adjust if using xterm/konsole)
        subprocess.Popen(["gnome-terminal", "--", "bash", script_path])
    elif system == "Darwin":  # macOS
        # Launch in a new Terminal window via AppleScript
        subprocess.Popen([
            "osascript", "-e",
            f'tell app "Terminal" to do script "bash {script_path}"'
        ])
    else:
        # Fallback: run in current terminal
        subprocess.Popen(["bash", script_path])

def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(project_root, ".venv")

    create_venv(project_root, venv_dir)

    python_path = os.path.join(venv_dir, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv_dir, "bin", "python")
    if not os.path.exists(python_path):
        print(f"Virtual environment not found at {python_path}")
        sys.exit(1)

    install_requirements(python_path, project_root)

    # Pre-resolve script paths inside bat_scripts/
    server_script = os.path.join(project_root, "bat_scripts", "run_server.bat" if os.name == "nt" else "run_server.sh")
    client_script = os.path.join(project_root, "bat_scripts", "run_client.bat" if os.name == "nt" else "run_client.sh")

    while True:
        print("\n=== Launcher Menu ===")
        print("1. Spawn Server")
        print("2. Spawn Client")
        print("3. Generate Certificates")
        print("4. Exit")

        choice = input("Select an option: ").strip()

        if choice == "1":
            spawn_process(server_script)
        elif choice == "2":
            spawn_process(client_script)
        elif choice == "3":
            certs_dir = os.path.join(project_root, "certs")
            gen_cert_script = os.path.join(certs_dir, "gen_cert.py")
            if os.path.exists(gen_cert_script):
                subprocess.run([python_path, gen_cert_script])
            else:
                print("gen_cert.py not found in certs folder.")
        elif choice == "4":
            print("Exiting launcher.")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
