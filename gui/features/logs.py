import os
import tkinter as tk
from tkinter import messagebox
from datetime import datetime


def log_action(logs_dir, action, target):

    os.makedirs(logs_dir, exist_ok=True)

    log_path = os.path.join(logs_dir, "history.log")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {action} {target}\n")


def view_logs(
    root,
    logs_dir,
    APP_BG,
    CARD_BG,
    ACCENT,
    ACCENT_TEXT
):

    os.makedirs(logs_dir, exist_ok=True)

    log_path = os.path.join(logs_dir, "history.log")

    if not os.path.exists(log_path):
        open(log_path, "w").close()

    win = tk.Toplevel(root)

    win.title("Logs")
    win.geometry("720x500")
    win.configure(bg=APP_BG)

    text = tk.Text(
        win,
        bg=CARD_BG,
        fg="#EAEAEA",
        insertbackground="white",
        font=("Consolas", 10),
        padx=10,
        pady=10,
        relief="flat"
    )

    text.pack(
        fill="both",
        expand=True,
        padx=10,
        pady=10
    )

    # COLORS
    text.tag_config(
        "danger",
        foreground="#FF6B6B"
    )

    text.tag_config(
        "success",
        foreground="#7CFC92"
    )

    text.tag_config(
        "download",
        foreground="#8AB4FF"
    )

    text.tag_config(
        "normal",
        foreground="#EAEAEA"
    )

    def load_logs():

        text.delete("1.0", tk.END)

        with open(
            log_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            lines = f.readlines()

        for line in lines:

            clean = line.strip()

            if not clean:
                continue

            lower = clean.lower()

            if (
                "failed" in lower
                or "locked" in lower
                or "denied" in lower
            ):
                tag = "danger"

            elif (
                "encrypt" in lower
                or "decrypt" in lower
                or "create" in lower
            ):
                tag = "success"

            elif "download" in lower:
                tag = "download"

            else:
                tag = "normal"

            text.insert(
                tk.END,
                clean + "\n\n",
                tag
            )

    def clear_logs():

        if messagebox.askyesno(
            "Confirm",
            "Clear all logs?"
        ):

            open(log_path, "w").close()

            load_logs()

    btn_frame = tk.Frame(
        win,
        bg=APP_BG
    )

    btn_frame.pack(fill="x")

    tk.Button(
        btn_frame,
        text="Refresh",
        bg=ACCENT,
        fg=ACCENT_TEXT,
        command=load_logs
    ).pack(
        side="left",
        padx=10,
        pady=5
    )

    tk.Button(
        btn_frame,
        text="Clear Logs",
        bg="#d9534f",
        fg="white",
        command=clear_logs
    ).pack(
        side="left",
        padx=10,
        pady=5
    )

    load_logs()