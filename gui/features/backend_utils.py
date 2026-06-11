import subprocess
from tkinter import messagebox


def check_backend(executable):
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        subprocess.run(
            [executable],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags
        )
        return True

    except Exception:
        messagebox.showerror(
            "Error",
            "Encryption engine missing or blocked"
        )
        return False


def run_command(cmd):
    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        creationflags=creationflags
    )

    if result.returncode != 0:
        raise Exception(
            result.stderr if result.stderr else "Operation failed"
        )

    return result