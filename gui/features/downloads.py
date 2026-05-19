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