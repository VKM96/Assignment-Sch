# tcp/udp echo server and client {#mainpage}

This repository contains Source Code for a simple tcp/udp echo sever and client [Github-link](https://github.com/VKM96/Assignment-Sch)
The requirements are based on the assignment questions here [Assignment](Docs/Assignment_Edge.pdf)

## Table of contents

- [Context](#context)
- [Project-structure](#project-structure)
- [Code-flow](#code-flow)
- [Build-Instruction](#build-instruction)
- [Documentation](#docs)
- [Demo](#demo)
- [Contact-Me](#contact-me)

## Context

### server

1. Supports processing of multiple tcp, tcp_tls and udp connections and echoes the data back to the client. see implementation inside `src_server/`
2. Multi-connection support is built on an event-driven paradigm built atop selectors module in a single thread of execution. See `server.py` and `server_handlers.py`
3. Basic validation of the payload takes place rejecting large(>4096B) and non-unicode characters. See `server_payload_validator.py`
4. logs are implemented through inbuilt logging module, sensitive data protection, log rotation needs to be implemented. See `server_logging.py`
5. Environment variables saved in .env are used for configuring host, port, security params and other attributes. systemd is not used for config and managed within the app, See `server_config.py` and `.env`
6. tcp_tls connection uses self-signed certificates for SSL, and has an auth mechanism built on tops of JSON Web Tokens(JWT). See `server_authenticator.py`
7. tcp and udp connections do not have any auth mechanism. plain tcp needs to be removed, auth needs to be incorporated into udp as well
8. Rate-limiting is currently implemented using a fixed window strategy as a POC. Better strategies exist. See `server_rate_limiter.py`
9. Linux-Integration is done with a bare-minimal systemd file which handles only setup and execution. Users and security improvements pending. See `myapp.service`
10. Error-handling and management improvements yet to be done

### client

1. client is built as a cli application supporting udp, tcp and tcp_tls operations. see implementation inside `src_client/`
2. The connect, send and receive do not have any error handling, recovery mechanisms currently. This needs to be implemented
3. logs are implemented through inbuilt logging module, sensitive data protection needs to be implemented
4. Environment variables are taken from .env for demonstration. This will require more thought
5. tcp_tls ensures tls handshake is complete, and the auth token validated right at the point of connection.
6. Auth token is derived based on client_id unique to the client (settable) and .env based JWT_secret and JWT_algorithm
7. tcp and udp connections do not have any auth mechanism. plain tcp needs to be removed, auth needs to be incorporated into udp as well

![logs](Docs/Assets/logs.png)

## Project-structure

```text

+---.venv
+---archive
+---bat_scripts
+---certs
+---demo
+---docs
+---logs
+---misc
+---src_client
+---src_server

```

1. All source files for server are under `myapp/src_src/`, client under `myapp/src_client/`. They are developed as independent modules
2. Both modules contain `.env` inside their respective folders for environment variables
3. The server module is broken down into dedicated files segregated by feature for ease of maintenance
4. root folder houses `setup.sh` setting up project environment. 
5. `bat_scripts` contains batch files and shell scripts for quickly launching server and client
6. log locations are determined though `.env` they are currently set to `/var/log/myapp/` as instructed
7. `certs` contains config files and helper python script `gen_cert.py` for certificate generation, along with generated certificates
8. Systemd file `myapp.service` is housed inside misc folder
9. docs for documentation
10. demo contains demo_videos

## Code-flow

1. To be documented with illustration

## Build-Instruction

### Pre-requisite setup

- Place project folder under `/opt`
- Place the custom systemd service file `myapp.service` currently at `/opt/myapp/misc` into `/etc/systemmd/system`
- To install `myapp.service` run `systemctl daemon-reload`

### How to set-up and run the server client

#### set-up of server and client

- If installed as a service the prerequisite initialization script `setup.sh --init` is already invoked in `myapp.service` as part of `ExecStartPre`
- Internally it creates the log directory
- Sets up and activates the virtual environment
- Installs required packages though `requirements.txt`

![setup.sh --init](Docs/Assets/setup_init.png)

#### Run server

- If Installed as a service `systemctl start myapp.service` to start, `systemctl stop myapp.service` to stop
- `.\setup.sh --menu` launches a CLI, select option-1 to launch server
- `.\run_server.sh` inside `bat_scripts` folder can also run the server
- `python -m src_server.server` is the direct way to invoke the server, assuming all dependencies from `requirements.txt` are met

![systemctl](Docs/Assets/systemctl.png)

#### Run client

- `.\setup.sh --menu` launches a CLI, select option-2 to launch client
- `.\run_client.sh` inside `bat_scripts` folder can also run the client
- `python -m src_client.client` is the direct way to invoke the server, assuming all dependencies from `requirements.txt` are met

![client](Docs/Assets/client.png)

### How to generate TLS certificates

- `.\setup.sh --menu` launches a CLI, select option-2 to launch client
- It invokes `python gen_cert.py` in the certs folder
- Internally openssl with file openssl.cnf inside certs folder is used `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -config openssl.cnf`

![client](Docs/Assets/Certificate_Generation.png)

### How authentication works

- Authentication is built on the client end using JSON Web Tokens(JWT)
- JwT secret, algorithm and expirations are stored as environment variables
- Each client is associated with a client_ID which can be set at runtime  
- The client creates a JWT encoded token using the client_id and the expiration time as payload
- AUTH \<token\> is the first message shared by client when communicating over tls
- The server uses the same JW secret and algorithm to decode the upcoming AUTH token to authenticate the client

### How to run secure_check.sh

#### Invoking secure_check.sh

- run `.\secure_check.sh`

#### How secure_check.sh works

- Ports, log files and certificates to check are directly loaded from .env file
- `myapp.service` is checked internally for service status through `systemctl`
- ports are checked by `grep` for required ports on the output of `ss`
- file permissions are checked using `stat`

![securecheck](Docs/Assets/secure_check.png)

## Docs

1. pdf docs yet to be generated

## Demo

1. [Linux-Demo](demo/App_Demo_Linux.webm)
1. [App-Demo-Detailed](demo/App_Demo.mp4)

## Contact-Me

- <vishalbhatta@gmail.com> over E-Mail
- [LinkedIn](https://in.linkedin.com/in/vishal-keshava-murthy-8a2ba1a7)
