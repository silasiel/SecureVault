import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gui"))
import vault_manager


class VaultManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        vault_manager.APPDATA_DIR = self.temp_dir.name
        vault_manager.VAULT = os.path.join(self.temp_dir.name, "vault")
        vault_manager.LOGS = os.path.join(self.temp_dir.name, "logs")
        vault_manager.MASTER_PASSWORD_FILE = os.path.join(self.temp_dir.name, "master_password.json")
        vault_manager.VAULT_METADATA_FILE = os.path.join(self.temp_dir.name, "vault_metadata.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_new_vault_password_and_recovery(self):
        recovery_key = vault_manager.create_master_password("old-password")
        self.assertEqual(len(recovery_key.replace("-", "")), 64)
        self.assertTrue(vault_manager.verify_master_password("old-password"))
        self.assertFalse(vault_manager.verify_master_password("wrong-password"))

        vault_key = vault_manager.unlock_vault("old-password")
        self.assertIsNotNone(vault_key)
        self.assertEqual(len(vault_key), 64)

        recovered_key = vault_manager.recover_vault(recovery_key, "new-password")
        self.assertEqual(recovered_key, vault_key)
        self.assertFalse(vault_manager.verify_master_password("old-password"))
        self.assertTrue(vault_manager.verify_master_password("new-password"))
        self.assertEqual(vault_manager.unlock_vault("new-password"), vault_key)

    def test_password_change_keeps_vault_key(self):
        vault_manager.create_master_password("old-password")
        vault_key = vault_manager.unlock_vault("old-password")

        self.assertTrue(vault_manager.change_master_password("old-password", "new-password"))
        self.assertFalse(vault_manager.verify_master_password("old-password"))
        self.assertTrue(vault_manager.verify_master_password("new-password"))
        self.assertEqual(vault_manager.unlock_vault("new-password"), vault_key)

    def test_recovery_key_normalization_and_replacement(self):
        recovery_key = vault_manager.create_master_password("password")
        normalized = recovery_key.replace("-", "").lower()
        self.assertEqual(vault_manager.normalize_recovery_key(normalized), normalized.upper())

        new_recovery_key = vault_manager.regenerate_recovery_key("password")
        self.assertNotEqual(new_recovery_key, recovery_key)
        with self.assertRaises(ValueError):
            vault_manager.recover_vault(recovery_key, "another-password")

    def test_registered_files_use_vault_key_and_legacy_files_use_password(self):
        vault_manager.create_master_password("password")
        vault_manager.register_encrypted_file("folder", "new.txt.enc")

        self.assertEqual(
            vault_manager.get_file_encryption_secret("password", "folder", "new.txt.enc"),
            vault_manager.unlock_vault("password")
        )
        self.assertEqual(
            vault_manager.get_file_encryption_secret("password", "folder", "old.txt.enc"),
            "password"
        )

    def test_registered_file_paths_follow_moves_and_deletes(self):
        vault_manager.create_master_password("password")
        vault_manager.register_encrypted_file("main", "file.txt.enc")

        vault_manager.move_registered_file("main", "file.txt.enc", "archive")
        metadata = vault_manager.load_vault_metadata()
        self.assertIn("archive/file.txt.enc", metadata["encrypted_files"])
        self.assertNotIn("main/file.txt.enc", metadata["encrypted_files"])

        vault_manager.unregister_encrypted_file("archive", "file.txt.enc")
        self.assertNotIn("archive/file.txt.enc", vault_manager.load_vault_metadata()["encrypted_files"])

    def test_native_encryptor_round_trip_uses_vault_key(self):
        recovery_key = vault_manager.create_master_password("password")
        source_path = os.path.join(self.temp_dir.name, "sample.txt")
        output_path = os.path.join(self.temp_dir.name, "restored.txt")
        with open(source_path, "w", encoding="utf-8") as f:
            f.write("vault-key integration test")

        executable = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "encryptor.exe"))
        vault_manager.encrypt_files([source_path], "folder", vault_manager.get_vault_encryption_secret("password"), executable)

        encrypted_path = os.path.join(vault_manager.VAULT, "folder", "sample.txt.enc")
        result = subprocess.run(
            [
                executable,
                "decrypt",
                encrypted_path,
                output_path,
                vault_manager.get_file_encryption_secret("password", "folder", "sample.txt.enc")
            ],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )

        self.assertEqual(result.returncode, 0)
        with open(output_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "vault-key integration test")
        self.assertTrue(recovery_key)


if __name__ == "__main__":
    unittest.main()
