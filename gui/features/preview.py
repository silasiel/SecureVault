import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import tempfile
import shutil

try:
    from PIL import Image, ImageTk  # type: ignore[import]
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp"
}


def is_image_file(file_name):
    lower = file_name.lower()
    return any(lower.endswith(ext + ".enc") for ext in IMAGE_EXTS) or any(lower.endswith(ext) for ext in IMAGE_EXTS)


def preview_file(
    root,
    executable,
    base_vault,
    current_folder,
    file,
    APP_BG,
    CARD_BG,
    TEXT_PRIMARY,
    ask_password=None
):

    path = os.path.join(
        base_vault,
        current_folder,
        file
    )

    if is_image_file(file):
        if ask_password is None:
            messagebox.showinfo(
                "Preview Not Available",
                "Image preview requires a password prompt."
            )
            return

        password = ask_password(
            root,
            APP_BG,
            TEXT_PRIMARY,
            TEXT_PRIMARY,
            TEXT_PRIMARY,
            TEXT_PRIMARY,
            title="Image Preview",
            prompt=f"Enter password for '{file}'"
        )

        if not password:
            return

        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, file[:-4] if file.lower().endswith('.enc') else file)

        result = subprocess.run(
            [executable, "decrypt", path, temp_path, password],
            capture_output=True,
            text=True
        )

        if result.returncode != 0 or not os.path.exists(temp_path):
            shutil.rmtree(temp_dir, ignore_errors=True)
            messagebox.showerror(
                "Preview Failed",
                result.stderr or "Unable to decrypt image for preview."
            )
            return

        win = tk.Toplevel(root)
        win.title("Image Preview")
        win.configure(bg=APP_BG)

        def cleanup():
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", cleanup)

        if PIL_AVAILABLE:
            try:
                img = Image.open(temp_path)
                img = img.copy()
                img.thumbnail((800, 600), Image.ANTIALIAS)
                photo = ImageTk.PhotoImage(img)
                label = tk.Label(win, image=photo, bg=APP_BG)
                label.image = photo
                label.pack(fill="both", expand=True)
                return
            except Exception:
                pass

        if file.lower().endswith(('.png', '.gif')):
            try:
                photo = tk.PhotoImage(file=temp_path)
                label = tk.Label(win, image=photo, bg=APP_BG)
                label.image = photo
                label.pack(fill="both", expand=True)
                return
            except Exception:
                pass

        shutil.rmtree(temp_dir, ignore_errors=True)
        messagebox.showerror(
            "Preview Failed",
            "Unable to display image. Install Pillow for better image preview support."
        )
        return

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