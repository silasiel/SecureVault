import os
import shutil

from tkinter import filedialog, messagebox


def download_file(
    base_vault,
    current_folder,
    file,
    log_action,
    logs_dir
):
    src = os.path.join(
        base_vault,
        current_folder,
        file
    )

    dest = filedialog.asksaveasfilename(
        initialfile=file
    )

    if not dest:
        return

    shutil.copy2(src, dest)

    log_action(
        logs_dir,
        "DOWNLOAD_ENCRYPTED_FILE",
        file
    )

    messagebox.showinfo(
        "Success",
        "Encrypted file downloaded"
    )

def export_backup(
    base_vault,
    logs_dir,
    log_action
):
    dest = filedialog.askdirectory(
        title="Select backup destination"
    )

    if not dest:
        return

    target = os.path.join(dest, "SecureVaultBackup")

    if os.path.exists(target):
        confirm = messagebox.askyesno(
            "Overwrite Backup",
            f"A backup already exists at:\n{target}\n\nOverwrite?"
        )

        if not confirm:
            return

    shutil.copytree(
        base_vault,
        target,
        dirs_exist_ok=True
    )

    log_action(
        logs_dir,
        "EXPORT_BACKUP",
        target
    )

    messagebox.showinfo(
        "Success",
        f"Vault backup exported to:\n{target}"
    )


def count_backup_items(path):
    file_count = 0
    folder_count = 0

    for root_dir, dirs, files in os.walk(path):
        folder_count += len(dirs)
        file_count += len(files)

    return folder_count, file_count


def find_backup_root(src):
    if os.path.basename(src) == "SecureVaultBackup":
        return src

    candidate = os.path.join(src, "SecureVaultBackup")
    if os.path.isdir(candidate):
        return candidate

    for entry in os.listdir(src):
        child = os.path.join(src, entry)
        candidate = os.path.join(child, "SecureVaultBackup")
        if os.path.isdir(candidate):
            return candidate

    return None


def import_backup(
    base_vault,
    logs_dir,
    log_action
):
    src = filedialog.askdirectory(
        title="Select backup source folder"
    )

    if not src:
        return False

    root_backup = find_backup_root(src)
    if root_backup is None:
        messagebox.showerror(
            "Error",
            "Selected folder does not contain a valid vault backup."
        )
        return False

    src = root_backup

    if not any(os.scandir(src)):
        messagebox.showerror(
            "Error",
            "Selected backup is empty."
        )
        return False

    folder_count, file_count = count_backup_items(src)

    confirm = messagebox.askyesno(
        "Import Backup",
        f"This backup contains {folder_count} folders and {file_count} files.\n\nProceed with import?"
    )

    if not confirm:
        return False

    for item in os.listdir(src):
        source_item = os.path.join(src, item)
        dest_item = os.path.join(base_vault, item)

        if os.path.exists(dest_item):
            confirm = messagebox.askyesno(
                "Overwrite Existing Data",
                f"'{item}' already exists in the vault. Overwrite?"
            )

            if not confirm:
                continue

            if os.path.isdir(dest_item):
                shutil.rmtree(dest_item)
            else:
                os.remove(dest_item)

        if os.path.isdir(source_item):
            shutil.copytree(
                source_item,
                dest_item,
                dirs_exist_ok=True
            )
        else:
            shutil.copy2(source_item, dest_item)

    log_action(
        logs_dir,
        "IMPORT_BACKUP",
        src
    )

    messagebox.showinfo(
        "Success",
        "Vault backup imported successfully."
    )

    return True

def download_folder(
    base_vault,
    folder,
    log_action,
    logs_dir
):
    src = os.path.join(base_vault, folder)

    dest = filedialog.askdirectory()

    if not dest:
        return

    target = os.path.join(dest, folder)

    shutil.copytree(
        src,
        target,
        dirs_exist_ok=True
    )

    log_action(
        logs_dir,
        "DOWNLOAD_FOLDER",
        folder
    )

    messagebox.showinfo(
        "Success",
        "Encrypted folder downloaded"
    )