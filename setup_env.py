# setup_env.py
import os
import sys
import subprocess
import platform

def get_python_path(venv_dir):
    if platform.system() == "Windows":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        return os.path.join(venv_dir, "bin", "python")

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

def spawn_process(python_path, script_name):
    if platform.system() == "Windows":
        subprocess.Popen(["start", "cmd", "/k", python_path, script_name], shell=True)
    else:
        subprocess.Popen(["gnome-terminal", "--", python_path, script_name])

def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(project_root, ".venv")

    create_venv(project_root, venv_dir)
    python_path = get_python_path(venv_dir)

    if not os.path.exists(python_path):
        print(f"Virtual environment not found at {python_path}")
        print("Run: python -m venv .venv")
        sys.exit(1)

    install_requirements(python_path, project_root)

    while True:
        print("\n=== Launcher Menu ===")
        print("1. Spawn Server")
        print("2. Spawn Client")
        print("3. Spawn Multiple Clients")
        print("4. Generate Certificates")
        print("5. Exit")

        choice = input("Select an option: ").strip()

        if choice == "1":
            spawn_process(python_path, "server.py")
        elif choice == "2":
            spawn_process(python_path, "client.py")
        elif choice == "3":
            try:
                count = int(input("How many clients to spawn? "))
                for _ in range(count):
                    spawn_process(python_path, "client.py")
            except ValueError:
                print("Invalid number.")
        elif choice == "4":
            # Run gen_cert.py inside certs folder
            certs_dir = os.path.join(project_root, "certs")
            gen_cert_script = os.path.join(certs_dir, "gen_cert.py")
            if os.path.exists(gen_cert_script):
                subprocess.run([python_path, gen_cert_script])
            else:
                print("gen_cert.py not found in certs folder.")
        elif choice == "5":
            print("Exiting launcher.")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
