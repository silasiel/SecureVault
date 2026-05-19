import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import subprocess
import sys
import os
import threading
import shutil

from tkinterdnd2 import TkinterDnD, DND_FILES

from theme import *
from vault_manager import *

from features.logs import *
from features.security import *
from features.password_ui import *
from features.preview import *
from features.downloads import *
from features.search import *


# PATH
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


if getattr(sys, 'frozen', False):
    EXECUTABLE = os.path.join(BASE_DIR, "encryptor.exe")
else:
    EXECUTABLE = os.path.join(BASE_DIR, "build", "encryptor.exe")


APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA"), "SecureVault")
BASE_VAULT = os.path.join(APPDATA_DIR, "vault")
LOGS_DIR = os.path.join(APPDATA_DIR, "logs")

ensure_vault()

selected_files = []
current_folder = None


# GUI
root = TkinterDnD.Tk()
progress_var = tk.DoubleVar()
search_var = tk.StringVar()

root.title("SECURE VAULT")
root.geometry("1150x720")
root.configure(bg=APP_BG)


# UTIL

def check_backend():
    try:
        subprocess.run(
            [EXECUTABLE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True

    except Exception:
        messagebox.showerror(
            "Error",
            "Encryption engine missing or blocked"
        )
        return False


# FILE SELECT

def select_files():
    global selected_files

    files = filedialog.askopenfilenames()

    if files:
        selected_files = list(files)

        status_label.config(
            text=f"{len(files)} files selected"
        )


# DRAG DROP

def handle_drop(event):
    global selected_files

    files = root.tk.splitlist(event.data)

    selected_files = list(files)

    status_label.config(
        text=f"{len(files)} files dropped"
    )


# FOLDERS

def create_new_folder():

    name = simpledialog.askstring(
        "Folder",
        "Folder name:"
    )

    if not name:
        return

    create_folder(name)

    pwd = simpledialog.askstring(
        "Set Password",
        f"Set password for '{name}':",
        show="*"
    )

    if pwd:
        set_folder_password(name, pwd)

        log_action(
            LOGS_DIR,
            "CREATE_SECURE_FOLDER",
            name
        )

    refresh_folders()



def open_folder(folder):
    global current_folder

    locked, remaining = is_folder_locked(folder)

    if locked:
        messagebox.showerror(
            "Vault Locked",
            f"Too many failed attempts.\n\nTry again in {remaining} seconds."
        )
        return

    result = verify_folder_password(folder, "")

    if result is None:

        pwd = simpledialog.askstring(
            "Set Password",
            f"Set password for '{folder}':",
            show="*"
        )

        if not pwd:
            return

        set_folder_password(folder, pwd)

    else:

        pwd = ask_password(
            root,
            APP_BG,
            TEXT_PRIMARY,
            TEXT_SECONDARY,
            ACCENT,
            ACCENT_TEXT
        )

        if not pwd:
            return

        if not verify_folder_password(folder, pwd):

            attempts = record_failed_attempt(
                folder,
                log_action,
                LOGS_DIR
            )

            messagebox.showerror(
                "Access Denied",
                f"Incorrect password\n\nAttempt {attempts} of 3"
            )

            return

    reset_failed_attempts(folder)

    current_folder = folder

    status_label.config(
        text=f"Opened: {folder}"
    )

    refresh_files()


# ENCRYPT

def encrypt_files_to_folder(password):

    if not selected_files:
        messagebox.showerror(
            "Error",
            "No files selected"
        )
        return

    if not current_folder:
        messagebox.showerror(
            "Error",
            "Select a folder"
        )
        return

    if not check_backend():
        return

    total = len(selected_files)

    try:

        for i, file in enumerate(selected_files):

            encrypt_files(
                [file],
                current_folder,
                password,
                EXECUTABLE
            )

            percent = ((i + 1) / total) * 100

            # UPDATE PROGRESS
            root.after(
                0,
                lambda p=percent: progress_var.set(p)
            )

            # REFRESH FILES IMMEDIATELY
            root.after(0, refresh_files)

        log_action(
            LOGS_DIR,
            "ENCRYPT_BATCH",
            f"{len(selected_files)} files -> {current_folder}"
        )

        root.after(
            0,
            lambda: status_label.config(
                text="Encryption complete"
            )
        )

        # RESET BAR AFTER SHORT DELAY
        root.after(
            1200,
            lambda: progress_var.set(0)
        )

    except Exception as e:

        root.after(
            0,
            lambda: messagebox.showerror(
                "Encryption Failed",
                str(e)
            )
        )


def run_encrypt_thread():

    password = ask_password(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT
    )

    if not password:
        return

    progress_var.set(0)

    threading.Thread(
        target=encrypt_files_to_folder,
        args=(password,)
    ).start()


# DECRYPT

def decrypt_file(file):

    if not check_backend():
        return

    password = ask_password(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT
    )

    if not password:
        return

    input_path = os.path.join(
        BASE_VAULT,
        current_folder,
        file
    )

    filename = file[:-4] if file.endswith(".enc") else file

    output = filedialog.asksaveasfilename(
        initialfile=filename
    )

    if not output:
        return

    result = subprocess.run(
        [EXECUTABLE, "decrypt", input_path, output, password],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:

        log_action(
            LOGS_DIR,
            "Failed decryption attempt:",
            file
        )

        messagebox.showerror(
            "Error",
            result.stderr or "Decryption failed"
        )

        return

    if os.path.exists(output):

        log_action(
            LOGS_DIR,
            "DECRYPT",
            file
        )

        os.startfile(output)


# DELETE

def delete_selected_file(file):

    delete_file(current_folder, file)

    log_action(
        LOGS_DIR,
        "DELETE",
        f"{current_folder}/{file}"
    )

    refresh_files()



def delete_selected_folder(folder):

    confirm = messagebox.askyesno(
        "Delete",
        f"Delete folder {folder}?"
    )

    if not confirm:
        return

    success = delete_folder(folder)

    if not success:
        messagebox.showerror(
            "Error",
            "Could not delete folder"
        )
        return

    log_action(
        LOGS_DIR,
        "DELETE_FOLDER",
        folder
    )

    refresh_folders()
    refresh_files()


# SEARCH

def filter_files(*args):
    refresh_files()


# REFRESH

def refresh_folders():

    for w in folder_list.winfo_children():
        w.destroy()

    for f in get_folders():

        frame = tk.Frame(folder_list, bg=SIDEBAR_BG)
        frame.pack(fill="x", pady=3)

        tk.Button(
            frame,
            text=f,
            bg=ACCENT,
            fg=ACCENT_TEXT,
            command=lambda folder=f: open_folder(folder)
        ).pack(side="left", fill="x", expand=True)

        tk.Button(
            frame,
            text="⬇️",
            bg=HIGHLIGHT,
            fg="black",
            command=lambda folder=f: download_folder(
                BASE_VAULT,
                folder,
                log_action,
                LOGS_DIR
            )
        ).pack(side="right", padx=2)

        tk.Button(
            frame,
            text="X",
            bg="#d9534f",
            fg="white",
            command=lambda folder=f: delete_selected_folder(folder)
        ).pack(side="right")



def refresh_files():

    for w in file_list_frame.winfo_children():
        w.destroy()

    if not current_folder:
        return

    search_query = search_var.get().lower()

    if search_query == "search files":
        search_query = ""

    files = []

    for f in get_files(current_folder):

        if f == ".meta":
            continue

        priority = 0

        if search_query and search_query in f.lower():
            priority = 1

        elif search_query:
            continue

        files.append((priority, f))

    files.sort(reverse=True)

    for _, f in files:

        highlight = (
            search_query
            and search_query in f.lower()
        )

        frame = tk.Frame(
            file_list_frame,
            bg="#5B4B8A" if highlight else CARD_BG,
            pady=6,
            padx=6
        )

        frame.pack(fill="x", padx=10, pady=4)

        tk.Label(
            frame,
            text=f,
            bg="#5B4B8A" if highlight else CARD_BG,
            fg="white" if highlight else TEXT_PRIMARY,
            font=("Segoe UI", 10, "bold" if highlight else "normal")
        ).pack(side="left")

        btn_frame = tk.Frame(
            frame,
            bg="#5B4B8A" if highlight else CARD_BG
        )

        btn_frame.pack(side="right")

        tk.Button(
            btn_frame,
            text="⬇️",
            bg=HIGHLIGHT,
            fg="black",
            command=lambda file=f: download_file(
                BASE_VAULT,
                current_folder,
                file,
                log_action,
                LOGS_DIR
            )
        ).pack(side="left", padx=3)

        tk.Button(
            btn_frame,
            text="Decrypt",
            bg=ACCENT,
            fg=ACCENT_TEXT,
            command=lambda file=f: decrypt_file(file)
        ).pack(side="left", padx=3)

        tk.Button(
            btn_frame,
            text="Preview",
            bg=ACCENT,
            fg=ACCENT_TEXT,
            command=lambda file=f: preview_file(
                root,
                EXECUTABLE,
                BASE_VAULT,
                current_folder,
                file,
                APP_BG,
                CARD_BG,
                TEXT_PRIMARY
            )
        ).pack(side="left", padx=3)

        tk.Button(
            btn_frame,
            text="Delete",
            bg="#d9534f",
            fg="white",
            command=lambda file=f: delete_selected_file(file)
        ).pack(side="left", padx=3)


# LAYOUT
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

sidebar = tk.Frame(root, bg=SIDEBAR_BG, width=260)
sidebar.grid(row=0, column=0, sticky="ns")
sidebar.grid_propagate(False)

main = tk.Frame(root, bg=APP_BG)
main.grid(row=0, column=1, sticky="nsew")


# SIDEBAR

tk.Label(
    sidebar,
    text="SECURE VAULT",
    bg=SIDEBAR_BG,
    fg=TEXT_PRIMARY,
    font=("Segoe UI", 16, "bold")
).pack(pady=15)


tk.Button(
    sidebar,
    text="Logs",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=lambda: view_logs(
        root,
        LOGS_DIR,
        APP_BG,
        CARD_BG,
        ACCENT,
        ACCENT_TEXT
    )
).pack(fill="x", padx=10, pady=5)

tk.Frame(
    sidebar,
    height=2,
    bg="#abadba"
).pack(fill="x", padx=10, pady=8)

tk.Button(
    sidebar,
    text="Select Files",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=select_files
).pack(fill="x", padx=10, pady=5)


tk.Button(
    sidebar,
    text="New Folder",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=create_new_folder
).pack(fill="x", padx=10, pady=5)

tk.Frame(
    sidebar,
    height=2,
    bg="#abadb1"
).pack(fill="x", padx=10, pady=8)

folder_list = tk.Frame(sidebar, bg=SIDEBAR_BG)
folder_list.pack(fill="both", expand=True)


# MAIN

drop = tk.Frame(
    main,
    bg=CARD_BG,
    height=260,
    bd=2,
    relief="ridge"
)

drop.pack(fill="x", padx=20, pady=15)


tk.Label(
    drop,
    text="Drag & Drop Files Here",
    bg=CARD_BG,
    fg=TEXT_PRIMARY,
    font=("Segoe UI", 16)
).pack(expand=True)


drop.drop_target_register(DND_FILES)
drop.dnd_bind("<<Drop>>", handle_drop)


tk.Button(
    main,
    text="Encrypt Files",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=run_encrypt_thread
).pack(pady=5)


search_bar = tk.Entry(
    main,
    textvariable=search_var,
    font=("Segoe UI", 11),
    fg="gray"
)

search_bar.insert(0, "Search files")
search_bar.pack(fill="x", padx=20, pady=5)


style = ttk.Style()
style.theme_use("default")

style.configure(
    "purple.Horizontal.TProgressbar",
    troughcolor="#382F64",
    background="#A598C0",
    bordercolor="#382F64",
    lightcolor="#B9AACF",
    darkcolor="#BDADD4"
)

progress = ttk.Progressbar(
    main,
    variable=progress_var,
    maximum=100,
    style="purple.Horizontal.TProgressbar"
)

progress.pack(fill="x", padx=20, pady=5)


file_list_frame = tk.Frame(main, bg=APP_BG)
file_list_frame.pack(fill="both", expand=True)


status_label = tk.Label(
    main,
    text="Ready",
    bg=APP_BG,
    fg=TEXT_SECONDARY
)

status_label.pack(pady=5)


search_var.trace_add("write", filter_files)

refresh_folders()

root.mainloop()
