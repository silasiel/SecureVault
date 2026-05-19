import subprocess
from tkinter import messagebox


def check_backend(executable):
    try:
        subprocess.run(
            [executable],
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


def run_command(cmd):
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(
            result.stderr if result.stderr else "Operation failed"
        )

    return result