import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import subprocess
import sys
import os
import threading
import shutil
import traceback

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

auth_ready = False
protected_controls = []
auth_loading_bar = None
auth_status_label = None
auth_window = None
auth_password_entry = None
auth_unlock_button = None
current_authentication_method = "Locked"
authentication_completion_callback = None

def startup_log(message):
    print(f"[SecureVault startup] {message}", flush=True)


def startup_call(label, func, *args, **kwargs):
    startup_log(f"BEFORE {label}")
    try:
        result = func(*args, **kwargs)
    except Exception:
        startup_log(f"EXCEPTION in {label}")
        traceback.print_exc()
        raise
    startup_log(f"AFTER {label}")
    return result


def startup_background_call(label, func, on_success=None, on_error=None):
    def worker():
        startup_log(f"THREAD BEFORE {label}")
        try:
            result = func()
        except Exception as exc:
            startup_log(f"THREAD EXCEPTION in {label}: {exc}")
            traceback.print_exc()
            if on_error is not None:
                root.after(0, lambda exc=exc: on_error(exc))
            return

        startup_log(f"THREAD AFTER {label}")
        if on_success is not None:
            root.after(0, lambda result=result: on_success(result))

    threading.Thread(target=worker, daemon=True).start()


startup_call("ensure_vault", ensure_vault)

selected_files = []
current_folder = MAIN_MENU_FOLDER
master_password = None
drag_state = {
    "source_folder": None,
    "file": None,
    "target_folder": None,
    "active": False,
}


# GUI
startup_log("BEFORE TkinterDnD.Tk()")
root = TkinterDnD.Tk()
startup_log("AFTER TkinterDnD.Tk()")
progress_var = tk.DoubleVar()
search_var = tk.StringVar()

root.title("SECURE VAULT")
root.geometry("1150x720")
root.configure(bg=APP_BG)


def is_authenticated():
    return auth_ready


def require_authentication(action_name):
    if is_authenticated():
        return True

    messagebox.showerror(
        "Vault Locked",
        f"Unlock the vault before using {action_name}."
    )
    return False


def register_protected_control(widget):
    protected_controls.append(widget)
    return widget


def set_protected_controls_enabled(enabled):
    state = "normal" if enabled else "disabled"

    for widget in protected_controls:
        try:
            widget.configure(state=state)
        except Exception:
            pass


def set_auth_loading(active, message="Verifying vault password..."):
    if auth_status_label is not None:
        auth_status_label.configure(
            text=message if active else "Vault unlocked"
        )

    if auth_loading_bar is not None:
        if active:
            auth_loading_bar.pack(fill="x", padx=20, pady=(0, 8))
            auth_loading_bar.start(10)
        else:
            auth_loading_bar.stop()
            auth_loading_bar.pack_forget()


def folder_label(folder):
    if folder == MAIN_MENU_FOLDER:
        return "Main Menu"
    return folder


def set_drag_target(folder):
    if drag_state["active"]:
        drag_state["target_folder"] = folder


def clear_drag_target(folder=None):
    if folder is None or drag_state["target_folder"] == folder:
        drag_state["target_folder"] = None


def begin_file_drag(source_folder, file):
    drag_state["source_folder"] = source_folder
    drag_state["file"] = file
    drag_state["target_folder"] = None
    drag_state["active"] = True


def finish_file_drag():
    source_folder = drag_state["source_folder"]
    file = drag_state["file"]
    target_folder = drag_state["target_folder"]

    drag_state["source_folder"] = None
    drag_state["file"] = None
    drag_state["target_folder"] = None
    drag_state["active"] = False

    if not source_folder or not file or not target_folder:
        return

    if target_folder == source_folder:
        return

    move_file_to_folder(source_folder, file, target_folder)


root.deiconify()
root.update_idletasks()


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


def set_auth_ready(ready):
    global auth_ready

    auth_ready = ready
    set_protected_controls_enabled(ready)

    if ready:
        set_auth_loading(False)
        status_label.config(text="Ready")
        if auth_window is not None and auth_window.winfo_exists():
            auth_window.destroy()
    else:
        set_auth_loading(False, "Authentication required")


def _show_authentication_screen():
    global auth_window, auth_password_entry, auth_unlock_button

    if auth_window is not None and auth_window.winfo_exists():
        auth_window.lift()
        return

    auth_window = tk.Toplevel(root)
    auth_window.title("Unlock Secure Vault")
    auth_window.geometry("420x300")
    auth_window.configure(bg=APP_BG)
    auth_window.transient(root)
    auth_window.protocol("WM_DELETE_WINDOW", root.destroy)

    tk.Label(
        auth_window,
        text="Unlock Secure Vault",
        bg=APP_BG,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 16, "bold")
    ).pack(pady=(22, 12))

    tk.Label(
        auth_window,
        text="Master Password",
        bg=APP_BG,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 11)
    ).pack()

    password_var = tk.StringVar()
    auth_password_entry = tk.Entry(
        auth_window,
        textvariable=password_var,
        show="*",
        width=32
    )
    auth_password_entry.pack(pady=8)

    def unlock_with_password():
        password = password_var.get()
        if not password:
            messagebox.showerror("Password", "Enter your master password.", parent=auth_window)
            return

        auth_unlock_button.configure(state="disabled")
        auth_status_label.configure(text="Verifying password...")

        def on_verified(is_valid):
            if is_valid:
                global current_authentication_method
                current_authentication_method = "Master Password"
                authentication_completed(password)
                return

            auth_unlock_button.configure(state="normal")
            auth_status_label.configure(text="Authentication required")
            messagebox.showerror("Access Denied", "Incorrect master password.", parent=auth_window)

        startup_background_call(
            "verify_master_password",
            lambda: verify_master_password(password),
            on_success=on_verified,
            on_error=lambda exc: on_authentication_error(exc)
        )

    auth_unlock_button = tk.Button(
        auth_window,
        text="Unlock",
        bg=ACCENT,
        fg=ACCENT_TEXT,
        command=unlock_with_password
    )
    auth_unlock_button.pack(pady=(2, 10))

    tk.Button(
        auth_window,
        text="Forgot Master Password?",
        bg=APP_BG,
        fg=ACCENT,
        relief="flat",
        command=show_recovery_screen
    ).pack(pady=(8, 0))

    auth_password_entry.bind("<Return>", lambda _event: unlock_with_password())
    auth_password_entry.focus_set()


def show_recovery_screen():
    recovery_window = tk.Toplevel(root)
    recovery_window.title("Recover Vault")
    recovery_window.geometry("420x260")
    recovery_window.configure(bg=APP_BG)
    recovery_window.transient(root)
    recovery_window.grab_set()

    tk.Label(
        recovery_window,
        text="RECOVER VAULT",
        bg=APP_BG,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 16, "bold")
    ).pack(pady=(22, 12))

    tk.Label(
        recovery_window,
        text="Recovery Key",
        bg=APP_BG,
        fg=TEXT_PRIMARY
    ).pack()

    recovery_entry = tk.Entry(recovery_window, width=38)
    recovery_entry.pack(pady=8)

    def show_new_password_form():
        recovery_value = recovery_entry.get()
        for widget in recovery_window.winfo_children():
            widget.destroy()

        tk.Label(
            recovery_window,
            text="CREATE NEW MASTER PASSWORD",
            bg=APP_BG,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 13, "bold")
        ).pack(pady=(18, 12))

        tk.Label(recovery_window, text="New Password", bg=APP_BG, fg=TEXT_PRIMARY).pack()
        new_entry = tk.Entry(recovery_window, show="*", width=32)
        new_entry.pack(pady=6)

        tk.Label(recovery_window, text="Confirm Password", bg=APP_BG, fg=TEXT_PRIMARY).pack()
        confirm_entry = tk.Entry(recovery_window, show="*", width=32)
        confirm_entry.pack(pady=6)

        def set_new_password():
            new_password = new_entry.get()
            if not new_password:
                messagebox.showerror("Password", "Password cannot be empty.", parent=recovery_window)
                return
            if new_password != confirm_entry.get():
                messagebox.showerror("Password", "Passwords do not match.", parent=recovery_window)
                return

            try:
                vault_key = recover_vault(recovery_value, new_password)
            except ValueError as exc:
                messagebox.showerror("Recovery", str(exc), parent=recovery_window)
                return
            except Exception:
                messagebox.showerror("Recovery", "Vault recovery failed.", parent=recovery_window)
                return

            del vault_key
            recovery_window.destroy()
            global current_authentication_method
            current_authentication_method = "Recovery Key"
            authentication_completed(new_password)

        tk.Button(
            recovery_window,
            text="Set New Password",
            bg=ACCENT,
            fg=ACCENT_TEXT,
            command=set_new_password
        ).pack(pady=12)
        new_entry.focus_set()

    def verify_recovery_key():
        try:
            normalize_recovery_key(recovery_entry.get())
        except ValueError:
            messagebox.showerror("Recovery", "Invalid Recovery Key.", parent=recovery_window)
            return

        if load_vault_metadata() is None:
            messagebox.showerror(
                "Recovery",
                "Recovery is not available for this legacy vault.",
                parent=recovery_window
            )
            return

        show_new_password_form()

    tk.Button(
        recovery_window,
        text="Verify Recovery Key",
        bg=ACCENT,
        fg=ACCENT_TEXT,
        command=verify_recovery_key
    ).pack(pady=12)
    recovery_entry.focus_set()


def on_authentication_error(exc):
    startup_log(f"Authentication error: {exc}")
    if auth_unlock_button is not None:
        auth_unlock_button.configure(state="normal")
    if auth_status_label is not None:
        auth_status_label.configure(text="Authentication required")


def authentication_completed(unlocked_password=None):
    if authentication_completion_callback is not None:
        authentication_completion_callback(unlocked_password)


def show_recovery_key_dialog(recovery_key, on_confirm):
    win = tk.Toplevel(root)
    win.title("Your Recovery Key")
    win.geometry("540x300")
    win.configure(bg=APP_BG)
    win.transient(root)
    win.grab_set()

    tk.Label(
        win,
        text="YOUR RECOVERY KEY",
        bg=APP_BG,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 15, "bold")
    ).pack(pady=(20, 12))

    key_var = tk.StringVar(value=recovery_key)
    tk.Entry(
        win,
        textvariable=key_var,
        state="readonly",
        justify="center",
        width=48,
        font=("Consolas", 11)
    ).pack(pady=8)

    tk.Label(
        win,
        text="This is the only recovery method if you forget your Master Password.\n"
             "Store this key somewhere secure. Anyone with it may be able to recover your vault.",
        bg=APP_BG,
        fg=TEXT_SECONDARY,
        justify="center",
        wraplength=480
    ).pack(pady=8)

    def copy_key():
        root.clipboard_clear()
        root.clipboard_append(recovery_key)
        messagebox.showinfo("Recovery Key", "Recovery Key copied to the clipboard.", parent=win)

    tk.Button(
        win,
        text="Copy Recovery Key",
        bg=ACCENT,
        fg=ACCENT_TEXT,
        command=copy_key
    ).pack(pady=6)

    tk.Button(
        win,
        text="I Stored My Recovery Key",
        bg=ACCENT,
        fg=ACCENT_TEXT,
        command=lambda: (win.destroy(), on_confirm())
    ).pack(pady=6)


def regenerate_recovery_key_screen(parent):
    try:
        recovery_key = regenerate_recovery_key(master_password)
    except ValueError as exc:
        messagebox.showerror("Recovery Key", str(exc), parent=parent)
        return
    except Exception:
        messagebox.showerror("Recovery Key", "Unable to generate a new Recovery Key.", parent=parent)
        return

    messagebox.showwarning(
        "Recovery Key Replaced",
        "The previous Recovery Key will stop working. Store the new key securely.",
        parent=parent
    )
    show_recovery_key_dialog(recovery_key, lambda: None)


def upgrade_legacy_vault_screen(parent=None):
    if not master_password:
        messagebox.showerror("Vault Locked", "Unlock the vault first.", parent=parent)
        return

    if load_vault_metadata() is not None:
        messagebox.showinfo("Vault Upgrade", "This vault is already upgraded.", parent=parent)
        return

    confirmed = messagebox.askyesno(
        "Upgrade Vault",
        "Your vault needs to be upgraded to support Recovery Key recovery.\n\n"
        "The encrypted files will be converted safely and verified before the upgrade is committed.\n\n"
        "Continue?",
        parent=parent
    )
    if not confirmed:
        return

    set_auth_loading(True, "Upgrading vault...")

    def worker():
        return migrate_legacy_vault(master_password, EXECUTABLE)

    def on_success(recovery_key):
        set_auth_loading(False)
        if parent is not None and parent.winfo_exists():
            parent.destroy()
        show_recovery_key_dialog(recovery_key, lambda: refresh_folders())

    def on_error(exc):
        set_auth_loading(False)
        messagebox.showerror("Vault Upgrade", str(exc), parent=parent)

    startup_background_call(
        "migrate_legacy_vault",
        worker,
        on_success=on_success,
        on_error=on_error
    )


def offer_legacy_vault_upgrade():
    try:
        is_legacy = load_vault_metadata() is None
    except ValueError as exc:
        messagebox.showerror("Vault Error", str(exc))
        return

    if is_legacy:
        messagebox.showinfo(
            "Legacy Vault",
            "Your vault needs to be upgraded to support Recovery Key recovery."
        )
        upgrade_legacy_vault_screen()


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
    if not require_authentication("folder creation"):
        return

    name = simpledialog.askstring(
        "Folder",
        "Folder name:"
    )

    if not name:
        return

    create_folder(name)

    log_action(
        LOGS_DIR,
        "CREATE_FOLDER",
        name
    )

    refresh_folders()


def ensure_main_menu_folder():
    os.makedirs(os.path.join(BASE_VAULT, MAIN_MENU_FOLDER), exist_ok=True)


def open_main_menu():
    global current_folder

    if not require_authentication("opening the main menu"):
        return

    ensure_main_menu_folder()
    current_folder = MAIN_MENU_FOLDER

    status_label.config(text="Opened: Main Menu")
    refresh_folders()
    refresh_files()



def open_folder(folder):
    global current_folder

    if folder == MAIN_MENU_FOLDER:
        open_main_menu()
        return

    if not require_authentication("opening folders"):
        return

    if folder not in get_folders():
        messagebox.showerror(
            "Error",
            "Folder does not exist"
        )
        return

    current_folder = folder

    status_label.config(
        text=f"Opened: {folder}"
    )

    refresh_folders()
    refresh_files()


def move_file_to_folder(source_folder, file, destination_folder):
    if not require_authentication("moving files"):
        return

    if destination_folder == source_folder:
        return

    source_path = os.path.join(BASE_VAULT, source_folder, file)
    destination_path = os.path.join(BASE_VAULT, destination_folder, file)

    if not os.path.exists(source_path):
        messagebox.showerror("Error", "Source file no longer exists.")
        return

    os.makedirs(os.path.join(BASE_VAULT, destination_folder), exist_ok=True)

    if os.path.exists(destination_path):
        confirm = messagebox.askyesno(
            "Overwrite File",
            f"'{file}' already exists in {folder_label(destination_folder)}. Overwrite it?"
        )

        if not confirm:
            return

        os.remove(destination_path)

    shutil.move(source_path, destination_path)
    move_registered_file(source_folder, file, destination_folder)

    log_action(
        LOGS_DIR,
        "MOVE_FILE",
        f"{file} -> {folder_label(destination_folder)}"
    )

    if current_folder == source_folder or current_folder == destination_folder:
        refresh_files()

    refresh_folders()


# ENCRYPT

def encrypt_files_to_folder(password):

    if not require_authentication("encryption"):
        return

    if not selected_files:
        messagebox.showerror(
            "Error",
            "No files selected"
        )
        return

    if not check_backend():
        return

    destination_folder = current_folder or MAIN_MENU_FOLDER
    ensure_main_menu_folder()

    total = len(selected_files)

    try:

        for i, file in enumerate(selected_files):

            encryption_secret = get_vault_encryption_secret(password)

            encrypt_files(
                [file],
                destination_folder,
                encryption_secret,
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
            f"{len(selected_files)} files -> {folder_label(destination_folder)}"
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

    if not require_authentication("encryption"):
        return

    if not master_password:
        messagebox.showerror(
            "Vault Locked",
            "Unlock the vault first."
        )
        return

    progress_var.set(0)

    threading.Thread(
        target=encrypt_files_to_folder,
        args=(master_password,)
    ).start()


# DECRYPT

def decrypt_file(file):

    if not require_authentication("decryption"):
        return

    if not check_backend():
        return

    password = verify_master_password_dialog(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT,
        title="Decrypt File",
        prompt=f"Re-enter your master password to decrypt '{file}':"
    )

    if not password:
        return

    if not verify_master_password(password):
        messagebox.showerror(
            "Access Denied",
            "Incorrect master password"
        )
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

    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    result = subprocess.run(
        [
            EXECUTABLE,
            "decrypt",
            input_path,
            output,
            get_file_encryption_secret(password, current_folder, file)
        ],
        capture_output=True,
        text=True,
        creationflags=creationflags
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

def authorize_master_password(action_title, prompt_text):

    if not require_authentication(action_title.lower()):
        return False

    if not master_password:
        messagebox.showerror(
            "Vault Locked",
            "Unlock the vault first."
        )
        return False

    pwd = verify_master_password_dialog(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT,
        title=action_title,
        prompt=prompt_text
    )

    if not pwd:
        return False

    if not verify_master_password(pwd):
        messagebox.showerror(
            "Access Denied",
            "Incorrect master password"
        )
        return False

    return True


def delete_selected_file(file):

    if not require_authentication("file deletion"):
        return

    if not current_folder:
        messagebox.showerror(
            "Error",
            "No folder selected"
        )
        return

    if not authorize_master_password(
        "Confirm Delete",
        f"Re-enter your master password to delete '{file}':"
    ):
        return

    path = os.path.join(
        BASE_VAULT,
        current_folder,
        file
    )

    success = secure_delete_file(path)

    if not success:
        messagebox.showerror(
            "Error",
            "Secure delete failed"
        )
        return

    delete_file(current_folder, file)
    unregister_encrypted_file(current_folder, file)
    log_action(
        LOGS_DIR,
        "DELETE_FILE",
        file
    )
    refresh_files()


def delete_selected_folder(folder):

    if not require_authentication("folder deletion"):
        return

    confirm = messagebox.askyesno(
        "Delete",
        f"Delete folder {folder}?"
    )

    if not confirm:
        return

    if not authorize_master_password(
        "Confirm Delete",
        f"Re-enter your master password to delete folder '{folder}':"
    ):
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
    if not is_authenticated():
        return

    refresh_files()


# REFRESH

def refresh_folders():
    if not is_authenticated():
        return

    for w in folder_list.winfo_children():
        w.destroy()

    main_menu_frame = tk.Frame(folder_list, bg=SIDEBAR_BG)
    main_menu_frame.pack(fill="x", pady=3)

    main_menu_button = tk.Button(
        main_menu_frame,
        text="Main Menu",
        bg=HIGHLIGHT if current_folder == MAIN_MENU_FOLDER else ACCENT,
        fg="black" if current_folder == MAIN_MENU_FOLDER else ACCENT_TEXT,
        command=open_main_menu
    )
    main_menu_button.pack(side="left", fill="x", expand=True)

    main_menu_frame.bind("<Enter>", lambda _event: set_drag_target(MAIN_MENU_FOLDER))
    main_menu_frame.bind("<Leave>", lambda _event: clear_drag_target(MAIN_MENU_FOLDER))
    main_menu_button.bind("<Enter>", lambda _event: set_drag_target(MAIN_MENU_FOLDER))
    main_menu_button.bind("<Leave>", lambda _event: clear_drag_target(MAIN_MENU_FOLDER))

    for f in get_folders():

        frame = tk.Frame(folder_list, bg=SIDEBAR_BG)
        frame.pack(fill="x", pady=3)

        frame.bind("<Enter>", lambda _event, folder=f: set_drag_target(folder))
        frame.bind("<Leave>", lambda _event, folder=f: clear_drag_target(folder))

        tk.Button(
            frame,
            text=f,
            bg=HIGHLIGHT if current_folder == f else ACCENT,
            fg="black" if current_folder == f else ACCENT_TEXT,
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
    if not is_authenticated():
        return

    for w in file_list_frame.winfo_children():
        w.destroy()

    if not current_folder:
        return

    source_folder = current_folder

    search_query = search_var.get().lower()

    if search_query == "search files":
        search_query = ""

    files = []

    for f in get_files(source_folder):

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

        frame.bind("<ButtonPress-1>", lambda _event, folder=source_folder, file=f: begin_file_drag(folder, file))
        frame.bind("<ButtonRelease-1>", lambda _event: finish_file_drag())
        frame.bind("<Button-3>", lambda event, folder=source_folder, file=f: show_file_context_menu(event, folder, file))

        label = tk.Label(
            frame,
            text=f,
            bg="#5B4B8A" if highlight else CARD_BG,
            fg="white" if highlight else TEXT_PRIMARY,
            font=("Segoe UI", 10, "bold" if highlight else "normal")
        )
        label.pack(side="left")

        label.bind("<ButtonPress-1>", lambda _event, folder=source_folder, file=f: begin_file_drag(folder, file))
        label.bind("<ButtonRelease-1>", lambda _event: finish_file_drag())
        label.bind("<Button-3>", lambda event, folder=source_folder, file=f: show_file_context_menu(event, folder, file))

        btn_frame = tk.Frame(
            frame,
            bg="#5B4B8A" if highlight else CARD_BG
        )

        btn_frame.pack(side="right")

        btn_frame.bind("<ButtonPress-1>", lambda _event, folder=source_folder, file=f: begin_file_drag(folder, file))
        btn_frame.bind("<ButtonRelease-1>", lambda _event: finish_file_drag())
        btn_frame.bind("<Button-3>", lambda event, folder=source_folder, file=f: show_file_context_menu(event, folder, file))

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
                TEXT_PRIMARY,
                get_file_encryption_secret(master_password, current_folder, file)
            )
        ).pack(side="left", padx=3)

        tk.Button(
            btn_frame,
            text="Shred",
            bg="#d9534f",
            fg="white",
            command=lambda file=f: delete_selected_file(file)
        ).pack(side="left", padx=3)


def show_file_context_menu(event, source_folder, file):
    menu = tk.Menu(root, tearoff=0)

    menu.add_command(
        label="Decrypt",
        command=lambda: decrypt_file(file)
    )
    menu.add_command(
        label="Preview",
        command=lambda: preview_file(
            root,
            EXECUTABLE,
            BASE_VAULT,
            source_folder,
            file,
            APP_BG,
            CARD_BG,
            TEXT_PRIMARY,
            get_file_encryption_secret(master_password, source_folder, file)
        )
    )

    add_menu = tk.Menu(menu, tearoff=0)
    available_folders = [folder for folder in get_folders() if folder != source_folder]

    if source_folder != MAIN_MENU_FOLDER:
        available_folders.insert(0, MAIN_MENU_FOLDER)

    for folder in available_folders:
        add_menu.add_command(
            label=folder_label(folder),
            command=lambda destination=folder: move_file_to_folder(source_folder, file, destination)
        )

    if available_folders:
        menu.add_cascade(label="Add to Folder", menu=add_menu)

    menu.add_separator()
    menu.add_command(
        label="Download",
        command=lambda: download_file(
            BASE_VAULT,
            source_folder,
            file,
            log_action,
            LOGS_DIR
        )
    )
    menu.add_command(
        label="Shred",
        command=lambda: delete_selected_file(file)
    )

    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def run_import_backup():
    if not require_authentication("backup import"):
        return

    if import_backup(
        BASE_VAULT,
        LOGS_DIR,
        log_action
    ):
        refresh_folders()
        refresh_files()


def open_security_settings():
    if not require_authentication("security settings"):
        return

    win = tk.Toplevel(root)
    win.title("Security Settings")
    win.geometry("480x300")
    win.configure(bg=APP_BG)
    win.transient(root)
    win.grab_set()

    tk.Label(
        win,
        text="Security Settings",
        bg=APP_BG,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 14, "bold")
    ).pack(pady=(15, 10))

    try:
        metadata = load_vault_metadata()
    except ValueError as exc:
        messagebox.showerror("Vault Error", str(exc), parent=win)
        win.destroy()
        return
    status_var = tk.StringVar(
        value=(
            "Master Password\nStatus: Configured\n\n"
            f"Recovery Key\nStatus: {'Configured' if metadata else 'Unavailable for legacy vault'}\n\n"
            f"Current Authentication Method\n{current_authentication_method}"
        )
    )

    status_label_local = tk.Label(
        win,
        textvariable=status_var,
        bg=APP_BG,
        fg=TEXT_SECONDARY,
        justify="left",
        wraplength=440,
        anchor="w"
    )
    status_label_local.pack(fill="x", padx=20, pady=(0, 15))

    tk.Button(
        win,
        text="Change Master Password",
        bg=ACCENT,
        fg=ACCENT_TEXT,
        command=change_master_password_screen
    ).pack(fill="x", padx=20, pady=8)

    if metadata is None:
        tk.Button(
            win,
            text="Upgrade Vault for Recovery Key",
            bg=ACCENT,
            fg=ACCENT_TEXT,
            command=lambda: upgrade_legacy_vault_screen(win)
        ).pack(fill="x", padx=20, pady=8)
    else:
        tk.Button(
            win,
            text="Generate New Recovery Key",
            bg=ACCENT,
            fg=ACCENT_TEXT,
            command=lambda: regenerate_recovery_key_screen(win)
        ).pack(fill="x", padx=20, pady=8)


root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

sidebar = tk.Frame(root, bg=SIDEBAR_BG, width=230)
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


logs_button = tk.Button(
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
)
logs_button.pack(fill="x", padx=10, pady=5)
register_protected_control(logs_button)

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


new_folder_button = tk.Button(
    sidebar,
    text="New Folder",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=create_new_folder
)
new_folder_button.pack(fill="x", padx=10, pady=5)
register_protected_control(new_folder_button)


tk.Frame(
    sidebar,
    height=2,
    bg="#abadb1"
).pack(fill="x", padx=10, pady=8)

folder_list = tk.Frame(sidebar, bg=SIDEBAR_BG)
folder_list.pack(fill="both", expand=True)


tk.Frame(
    sidebar,
    height=2,
    bg="#abadb1"
).pack(fill="x", padx=10, pady=8)


export_backup_button = tk.Button(
    sidebar,
    text="Export Backup",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=lambda: export_backup(
        BASE_VAULT,
        LOGS_DIR,
        log_action
    )
)
export_backup_button.pack(fill="x", padx=10, pady=5)
register_protected_control(export_backup_button)


import_backup_button = tk.Button(
    sidebar,
    text="Import Backup",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=run_import_backup
)
import_backup_button.pack(fill="x", padx=10, pady=5)
register_protected_control(import_backup_button)


security_settings_button = tk.Button(
    sidebar,
    text="Security Settings",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=open_security_settings
)
security_settings_button.pack(fill="x", padx=10, pady=5)
register_protected_control(security_settings_button)


def verify_password_screen():
    if not master_password:
        messagebox.showerror(
            "Vault Locked",
            "Unlock the vault first."
        )
        return

    pwd = verify_master_password_dialog(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT,
        title="Verify Master Password",
        prompt="Re-enter your master password to verify access:"
    )

    if not pwd:
        return

    if verify_master_password(pwd):
        messagebox.showinfo(
            "Verified",
            "Master password verified successfully."
        )
    else:
        messagebox.showerror(
            "Access Denied",
            "Incorrect master password"
        )


def change_master_password_screen():
    if not master_password:
        messagebox.showerror(
            "Vault Locked",
            "Unlock the vault first."
        )
        return

    current_password = startup_call(
        "verify_master_password_dialog",
        verify_master_password_dialog,
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT,
        title="Change Master Password",
        prompt="Enter your current master password:"
    )

    if not current_password:
        return

    set_auth_loading(True, "Verifying current password...")

    def on_current_password_verified(is_valid):
        if not is_valid:
            set_auth_loading(False, "Incorrect password")
            messagebox.showerror(
                "Access Denied",
                "Incorrect current master password"
            )
            return

        set_auth_loading(False)

        new_password = startup_call(
            "setup_master_password_dialog",
            setup_master_password_dialog,
            root,
            APP_BG,
            TEXT_PRIMARY,
            TEXT_SECONDARY,
            ACCENT,
            ACCENT_TEXT
        )

        if not new_password:
            return

        set_auth_loading(True, "Updating master password...")

        def on_password_changed(success):
            set_auth_loading(False)

            if not success:
                messagebox.showerror(
                    "Error",
                    "Unable to update the master password."
                )
                return

            global master_password
            master_password = new_password

            messagebox.showinfo(
                "Success",
                "Master password updated successfully."
            )

        startup_background_call(
            "change_master_password",
            lambda: change_master_password(current_password, new_password),
            on_success=on_password_changed,
            on_error=lambda exc: messagebox.showerror("Error", str(exc))
        )

    startup_background_call(
        "verify_current_master_password",
        lambda: verify_master_password(current_password),
        on_success=on_current_password_verified,
        on_error=lambda exc: messagebox.showerror("Error", str(exc))
    )


verify_password_button = tk.Button(
    sidebar,
    text="Verify Password",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=verify_password_screen
)
verify_password_button.pack(fill="x", padx=10, pady=5)
register_protected_control(verify_password_button)


change_password_button = tk.Button(
    sidebar,
    text="Change Password",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=change_master_password_screen
)
change_password_button.pack(fill="x", padx=10, pady=5)
register_protected_control(change_password_button)


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


encrypt_button = tk.Button(
    main,
    text="Encrypt Files",
    bg=ACCENT,
    fg=ACCENT_TEXT,
    command=run_encrypt_thread
)
encrypt_button.pack(pady=5)
register_protected_control(encrypt_button)


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


file_list_canvas = tk.Canvas(
    main,
    bg=APP_BG,
    highlightthickness=0
)

file_list_frame = tk.Frame(file_list_canvas, bg=APP_BG)
file_list_window = file_list_canvas.create_window((0, 0), window=file_list_frame, anchor="nw")

file_list_canvas.pack(fill="both", expand=True, padx=20, pady=(0, 0))


def _update_file_scrollregion(event=None):
    file_list_canvas.configure(scrollregion=file_list_canvas.bbox("all"))


def _resize_file_list_window(event=None):
    file_list_canvas.itemconfig(file_list_window, width=event.width)

file_list_frame.bind("<Configure>", _update_file_scrollregion)
file_list_canvas.bind("<Configure>", _resize_file_list_window)


def _on_file_list_mousewheel(event):
    if event.delta:
        file_list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    elif event.num == 4:
        file_list_canvas.yview_scroll(-1, "units")
    elif event.num == 5:
        file_list_canvas.yview_scroll(1, "units")

file_list_canvas.bind_all("<MouseWheel>", _on_file_list_mousewheel)
file_list_canvas.bind_all("<Button-4>", _on_file_list_mousewheel)
file_list_canvas.bind_all("<Button-5>", _on_file_list_mousewheel)


status_label = tk.Label(
    main,
    text="Ready",
    bg=APP_BG,
    fg=TEXT_SECONDARY
)

status_label.pack(pady=5)

auth_status_label = tk.Label(
    main,
    text="Preparing vault...",
    bg=APP_BG,
    fg=TEXT_SECONDARY
)

auth_status_label.pack(pady=(0, 5))

auth_loading_bar = ttk.Progressbar(
    main,
    mode="indeterminate",
    maximum=100,
    style="purple.Horizontal.TProgressbar"
)

auth_loading_bar.pack(fill="x", padx=20, pady=(0, 8))


search_var.trace_add("write", filter_files)

def initialize_auth_flow():
    global master_password, authentication_completion_callback

    startup_log("ENTER initialize_auth_flow")

    def complete_startup(unlocked_password=None):
        global master_password
        master_password = unlocked_password
        set_auth_ready(True)
        startup_log("BEFORE root.deiconify")
        root.deiconify()
        startup_log("AFTER root.deiconify")
        startup_call("open_main_menu", open_main_menu)
        root.after(250, offer_legacy_vault_upgrade)

    authentication_completion_callback = complete_startup

    try:
        has_password = startup_call("has_master_password", has_master_password)

        if not has_password:
            set_auth_loading(True, "Creating vault password...")
            setup_password = startup_call(
                "setup_master_password_dialog",
                setup_master_password_dialog,
                root,
                APP_BG,
                TEXT_PRIMARY,
                TEXT_SECONDARY,
                ACCENT,
                ACCENT_TEXT
            )

            if not setup_password:
                startup_log("Setup canceled; destroying root")
                root.destroy()
                return

            startup_background_call(
                "create_master_password",
                lambda: create_master_password(setup_password),
                on_success=lambda recovery_key: show_recovery_key_dialog(
                    recovery_key,
                    lambda: complete_startup(setup_password)
                ),
                on_error=lambda exc: (
                    messagebox.showerror("Startup Error", str(exc)),
                    root.destroy()
                )
            )
            return

        set_auth_ready(False)
        root.deiconify()
        _show_authentication_screen()

    except Exception:
        traceback.print_exc()
        root.destroy()


startup_log("BEFORE root.after initialize_auth_flow")
set_auth_ready(False)
root.after(150, initialize_auth_flow)
startup_log("AFTER root.after initialize_auth_flow")

startup_log("BEFORE root.mainloop")
root.mainloop()
startup_log("AFTER root.mainloop")
