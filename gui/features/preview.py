import tkinter as tk
import subprocess
import os


def preview_file(
    root,
    executable,
    base_vault,
    current_folder,
    file,
    APP_BG,
    CARD_BG,
    TEXT_PRIMARY
):

    path = os.path.join(
        base_vault,
        current_folder,
        file
    )

    result = subprocess.run(
        [executable, "preview", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    win = tk.Toplevel(root)

    win.title("Preview")
    win.geometry("650x450")
    win.configure(bg=APP_BG)

    text = tk.Text(
        win,
        bg=CARD_BG,
        fg=TEXT_PRIMARY,
        font=("Consolas", 10),
        padx=10,
        pady=10
    )

    text.pack(
        fill="both",
        expand=True
    )

    output = result.stdout.strip()

    if not output:
        output = "No preview available"

    text.insert(
        "1.0",
        output
    )