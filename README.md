# SecureVault
### Security Beyond Encryption

SecureVault is a desktop-based encrypted file management system designed to securely store, organize, encrypt, and protect sensitive digital files. The application combines a Python-based graphical interface with a C-powered encryption backend using OpenSSL cryptography libraries.

The project was built to address unauthorized access, accidental data leaks, insecure local storage, and weak file protection systems through modern encryption and security-focused system design. <br>
# Product Overview

SecureVault provides users with a secure desktop vault environment for handling confidential files locally while maintaining strong cryptographic security and usability.

The system integrates:
- AES-256-GCM authenticated encryption
- PBKDF2-HMAC-SHA256 password key derivation
- Intrusion detection systems
- Secure file shredding
- Encrypted backup export and recovery
- Real-time encryption tracking. <br>

# Features
* AES-GCM file encryption using OpenSSL
* Password-protected secure folders
* Drag-and-drop file support
* File preview functionality
* Secure file decryption
* Vault-based file organization
* Activity logging system
* Desktop GUI for ease of use
* Windows installer support <br>

# Installation Guide
### Method 1 — Installer
* Download SecureVault_Setup.exe from Releases
* Run the installer
* Launch SecureVault from Desktop or Start Menu
* If Windows SmartScreen appears, click: More Info → Run Anyway
### Method 2 — Running From Source
Requirements
 - Python 3.12+
 - MinGW GCC
 - OpenSSL
#### Steps
- Build C Backend
```bash
mingw32-make
```
- Run GUI
```bash
python gui/app.py
```
<br>

# Screenshots
To be added <br>

# Some Additional Security Notes
- Files are encrypted using AES-GCM authenticated encryption
- Password-protected folders prevent unauthorized access
- Sensitive data is stored locally on the user’s machine
- No cloud storage or external servers are used <br>

# License
This project is licensed under the MIT License.
