:: gen_cert.bat
@echo off
REM Generate self-signed certificate and key using OpenSSL

REM Ensure we’re in project root
cd /d %~dp0

REM Path to OpenSSL executable (adjust if installed elsewhere)
set OPENSSL=openssl

REM Check if openssl.cnf exists
if not exist "openssl.cnf" (
    echo Configuration file openssl.cnf not found in %~dp0
    exit /b 1
)

REM Run OpenSSL command
echo Generating server.crt and server.key...
%OPENSSL% req -new -x509 -days 365 -nodes -out server.crt -keyout server.key -config "openssl.cnf"

REM Check result
if %ERRORLEVEL% neq 0 (
    echo OpenSSL command failed.
    exit /b 1
)

echo Certificate and key generated successfully.
echo Files: server.crt, server.key
