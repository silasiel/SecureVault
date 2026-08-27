import os
import hashlib
import json
import secrets
import hmac
import subprocess
import shutil
import stat
import sys
import tempfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA"), "SecureVault")
VAULT = os.path.join(APPDATA_DIR, "vault")
LOGS = os.path.join(APPDATA_DIR, "logs")
MASTER_PASSWORD_FILE = os.path.join(APPDATA_DIR, "master_password.json")
VAULT_METADATA_FILE = os.path.join(APPDATA_DIR, "vault_metadata.json")
MAIN_MENU_FOLDER = "__main_menu__"
PBKDF2_ROUNDS = 200000
VAULT_FORMAT_VERSION = 2
VAULT_KEY_SIZE = 32
RECOVERY_KEY_SIZE = 32

def ensure_vault():
    os.makedirs(VAULT, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(os.path.join(VAULT, MAIN_MENU_FOLDER), exist_ok=True)


def has_master_password():
    return os.path.exists(MASTER_PASSWORD_FILE) or os.path.exists(VAULT_METADATA_FILE)


def _derive_master_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ROUNDS
    )


def _derive_wrapping_key(secret, salt, rounds=PBKDF2_ROUNDS):
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        rounds,
        dklen=VAULT_KEY_SIZE
    )


def _wrap_vault_key(secret, vault_key):
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    wrapping_key = _derive_wrapping_key(secret, salt)
    wrapped = AESGCM(wrapping_key).encrypt(nonce, vault_key, None)
    return {
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "rounds": PBKDF2_ROUNDS,
        "wrapped_key": wrapped.hex(),
    }


def _unwrap_vault_key(secret, wrapper):
    salt = bytes.fromhex(wrapper["salt"])
    nonce = bytes.fromhex(wrapper["nonce"])
    wrapped = bytes.fromhex(wrapper["wrapped_key"])
    wrapping_key = _derive_wrapping_key(secret, salt, int(wrapper["rounds"]))
    return AESGCM(wrapping_key).decrypt(nonce, wrapped, None)


def _atomic_write_json(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".securevault-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def load_vault_metadata():
    if not os.path.exists(VAULT_METADATA_FILE):
        return None

    try:
        with open(VAULT_METADATA_FILE, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as exc:
        raise ValueError("Vault metadata is corrupted.") from exc

    # If metadata exists but is an unsupported format or missing required fields,
    # treat the vault as a legacy/upgradeable vault instead of raising. Returning
    # None lets callers fall back to legacy behavior and allows the UI to offer
    # an explicit upgrade path.
    if metadata.get("vault_format_version") != VAULT_FORMAT_VERSION:
        return None

    if "password_wrapper" not in metadata or "recovery_wrapper" not in metadata:
        return None

    return metadata


def _new_vault_metadata(password):
    vault_key = secrets.token_bytes(VAULT_KEY_SIZE)
    recovery_key = secrets.token_bytes(RECOVERY_KEY_SIZE)
    return _metadata_for_vault_key(password, vault_key, recovery_key)


def _metadata_for_vault_key(password, vault_key, recovery_key=None, encrypted_files=None):
    if recovery_key is None:
        recovery_key = secrets.token_bytes(RECOVERY_KEY_SIZE)
    metadata = {
        "vault_format_version": VAULT_FORMAT_VERSION,
        "password_wrapper": _wrap_vault_key(password, vault_key),
        "recovery_wrapper": _wrap_vault_key(recovery_key.hex(), vault_key),
        "encrypted_files": encrypted_files or [],
    }
    return metadata, vault_key, format_recovery_key(recovery_key)

def format_recovery_key(raw_key):
    encoded = raw_key.hex().upper()
    return "-".join(encoded[index:index + 8] for index in range(0, len(encoded), 8))


def normalize_recovery_key(recovery_key):
    normalized = "".join(recovery_key.split()).replace("-", "").upper()
    if len(normalized) != RECOVERY_KEY_SIZE * 2:
        raise ValueError("Invalid Recovery Key.")
    try:
        bytes.fromhex(normalized)
    except ValueError as exc:
        raise ValueError("Invalid Recovery Key.") from exc
    return normalized


def create_master_password(password):
    ensure_vault()

    salt = secrets.token_bytes(16)
    password_hash = _derive_master_hash(password, salt)

    data = {
        "salt": salt.hex(),
        "hash": password_hash.hex()
    }

    _atomic_write_json(MASTER_PASSWORD_FILE, data)

    metadata, _, recovery_key = _new_vault_metadata(password)
    _atomic_write_json(VAULT_METADATA_FILE, metadata)
    return recovery_key


def _native_command(executable, command, input_path, output_path, password):
    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    result = subprocess.run(
        [executable, command, input_path, output_path, password],
        capture_output=True,
        creationflags=creationflags
    )
    if result.returncode != 0:
        raise RuntimeError("Vault migration verification failed.")


def _encrypted_vault_files(vault_root):
    files = []
    for folder, _, names in os.walk(vault_root):
        for name in names:
            if name.lower().endswith(".enc"):
                files.append(os.path.join(folder, name))
    return files


def migrate_legacy_vault(password, executable):
    if load_vault_metadata() is not None:
        raise ValueError("Vault is already upgraded.")

    if not verify_master_password(password):
        raise ValueError("Incorrect master password.")

    if not os.path.isdir(VAULT):
        raise ValueError("Vault data is unavailable.")

    staging_path = f"{VAULT}.migration-staging"
    backup_path = f"{VAULT}.migration-backup"
    shutil.rmtree(staging_path, ignore_errors=True)
    if os.path.exists(backup_path):
        raise ValueError("A previous vault migration needs recovery before retrying.")

    vault_key = secrets.token_bytes(VAULT_KEY_SIZE)
    recovery_key = secrets.token_bytes(RECOVERY_KEY_SIZE)
    encrypted_files = []

    try:
        shutil.copytree(VAULT, staging_path)
        plaintext_root = tempfile.mkdtemp(prefix="securevault-migration-")

        try:
            for source_path in _encrypted_vault_files(VAULT):
                relative_path = os.path.relpath(source_path, VAULT)
                staged_path = os.path.join(staging_path, relative_path)
                plain_path = os.path.join(plaintext_root, relative_path[:-4])
                verify_path = os.path.join(plaintext_root, "verify", relative_path[:-4])
                os.makedirs(os.path.dirname(plain_path), exist_ok=True)
                os.makedirs(os.path.dirname(verify_path), exist_ok=True)

                _native_command(executable, "decrypt", source_path, plain_path, password)
                _native_command(executable, "encrypt", plain_path, staged_path, vault_key.hex())
                _native_command(executable, "decrypt", staged_path, verify_path, vault_key.hex())

                with open(plain_path, "rb") as original, open(verify_path, "rb") as verified:
                    if original.read() != verified.read():
                        raise RuntimeError("Vault migration verification failed.")

                encrypted_files.append(relative_path.replace("\\", "/"))
        finally:
            shutil.rmtree(plaintext_root, ignore_errors=True)

        metadata, _, recovery_key_text = _metadata_for_vault_key(
            password,
            vault_key,
            recovery_key,
            sorted(encrypted_files)
        )
        _atomic_write_json(VAULT_METADATA_FILE, metadata)

        os.rename(VAULT, backup_path)
        try:
            os.rename(staging_path, VAULT)
        except Exception:
            os.rename(backup_path, VAULT)
            raise

        for migrated_path in _encrypted_vault_files(VAULT):
            relative_path = os.path.relpath(migrated_path, VAULT).replace("\\", "/")
            if relative_path not in encrypted_files:
                raise RuntimeError("Vault migration verification failed.")

        shutil.rmtree(backup_path, ignore_errors=True)
        return recovery_key_text
    except Exception:
        shutil.rmtree(staging_path, ignore_errors=True)
        if os.path.exists(backup_path):
            shutil.rmtree(VAULT, ignore_errors=True)
            os.rename(backup_path, VAULT)
        if os.path.exists(VAULT_METADATA_FILE):
            os.remove(VAULT_METADATA_FILE)
        raise


def change_master_password(current_password, new_password):
    if not verify_master_password(current_password):
        return False

    metadata = load_vault_metadata()
    if metadata is not None:
        try:
            vault_key = _unwrap_vault_key(current_password, metadata["password_wrapper"])
        except Exception:
            return False

        metadata["password_wrapper"] = _wrap_vault_key(new_password, vault_key)
        _atomic_write_json(VAULT_METADATA_FILE, metadata)

    salt = secrets.token_bytes(16)
    _atomic_write_json(MASTER_PASSWORD_FILE, {
        "salt": salt.hex(),
        "hash": _derive_master_hash(new_password, salt).hex(),
    })
    return True


def verify_master_password(password):
    metadata = load_vault_metadata()
    if metadata is not None:
        try:
            _unwrap_vault_key(password, metadata["password_wrapper"])
            return True
        except Exception:
            return False

    if not has_master_password():
        return False

    with open(MASTER_PASSWORD_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    salt = bytes.fromhex(data["salt"])
    expected = bytes.fromhex(data["hash"])
    candidate = _derive_master_hash(password, salt)

    return hmac.compare_digest(candidate, expected)


def unlock_vault(password):
    metadata = load_vault_metadata()
    if metadata is None:
        return password if verify_master_password(password) else None

    try:
        return _unwrap_vault_key(password, metadata["password_wrapper"]).hex()
    except Exception:
        return None


def get_vault_encryption_secret(password):
    return unlock_vault(password) or password


def recover_vault(recovery_key, new_password):
    metadata = load_vault_metadata()
    if metadata is None:
        raise ValueError("Recovery is not available for this legacy vault.")

    normalized = normalize_recovery_key(recovery_key)
    try:
        vault_key = _unwrap_vault_key(normalized.lower(), metadata["recovery_wrapper"])
    except Exception as exc:
        raise ValueError("Invalid Recovery Key.") from exc

    metadata["password_wrapper"] = _wrap_vault_key(new_password, vault_key)
    _atomic_write_json(VAULT_METADATA_FILE, metadata)

    salt = secrets.token_bytes(16)
    _atomic_write_json(MASTER_PASSWORD_FILE, {
        "salt": salt.hex(),
        "hash": _derive_master_hash(new_password, salt).hex(),
    })
    return vault_key.hex()


def regenerate_recovery_key(password):
    metadata = load_vault_metadata()
    if metadata is None:
        raise ValueError("Recovery key regeneration is not available for this legacy vault.")

    try:
        vault_key = _unwrap_vault_key(password, metadata["password_wrapper"])
    except Exception as exc:
        raise ValueError("Incorrect master password.") from exc

    recovery_key = secrets.token_bytes(RECOVERY_KEY_SIZE)
    metadata["recovery_wrapper"] = _wrap_vault_key(recovery_key.hex(), vault_key)
    _atomic_write_json(VAULT_METADATA_FILE, metadata)
    return format_recovery_key(recovery_key)


def get_file_encryption_secret(password, folder, file):
    metadata = load_vault_metadata()
    if metadata is None:
        return password

    relative_path = os.path.join(folder, file).replace("\\", "/")
    if relative_path in metadata.get("encrypted_files", []):
        return unlock_vault(password) or password
    return password


def register_encrypted_file(folder, file):
    metadata = load_vault_metadata()
    if metadata is None:
        return

    relative_path = os.path.join(folder, file).replace("\\", "/")
    if relative_path not in metadata["encrypted_files"]:
        metadata["encrypted_files"].append(relative_path)
        _atomic_write_json(VAULT_METADATA_FILE, metadata)


def move_registered_file(source_folder, file, destination_folder):
    metadata = load_vault_metadata()
    if metadata is None:
        return

    source_path = os.path.join(source_folder, file).replace("\\", "/")
    destination_path = os.path.join(destination_folder, file).replace("\\", "/")
    files = metadata.get("encrypted_files", [])

    if source_path in files:
        files.remove(source_path)
        if destination_path not in files:
            files.append(destination_path)
        _atomic_write_json(VAULT_METADATA_FILE, metadata)


def unregister_encrypted_file(folder, file):
    metadata = load_vault_metadata()
    if metadata is None:
        return

    relative_path = os.path.join(folder, file).replace("\\", "/")
    if relative_path in metadata.get("encrypted_files", []):
        metadata["encrypted_files"].remove(relative_path)
        _atomic_write_json(VAULT_METADATA_FILE, metadata)

def get_folders():
    ensure_vault()
    return [
        f for f in os.listdir(VAULT)
        if os.path.isdir(os.path.join(VAULT, f)) and f != MAIN_MENU_FOLDER
    ]


def create_folder(name):
    os.makedirs(os.path.join(VAULT, name), exist_ok=True)


def get_files(folder):
    path = os.path.join(VAULT, folder)
    if not os.path.exists(path):
        return []
    return os.listdir(path)


# ENCRYPT
def encrypt_files(files, folder, password, executable):
    folder_path = os.path.join(VAULT, folder)
    os.makedirs(folder_path, exist_ok=True)

    cmd = [executable, "encrypt_batch"]

    for f in files:
        cmd.append(os.path.abspath(f))

    cmd.append(folder_path)
    cmd.append(password)

    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    result = subprocess.run(cmd, creationflags=creationflags, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("Encryption failed.")

    for file in files:
        register_encrypted_file(folder, os.path.basename(file) + ".enc")

# DELETE
def delete_file(folder, file):
    path = os.path.join(VAULT, folder, file)
    if os.path.exists(path):
        os.remove(path)


def delete_folder(folder):
    path = os.path.join(VAULT, folder)

    if not os.path.exists(path):
        return False

    def handle_remove_readonly(func, path, exc):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except:
            pass

    try:
        shutil.rmtree(path, onerror=handle_remove_readonly)
        return True
    except Exception as e:
        print("Delete error:", e)
        return False


