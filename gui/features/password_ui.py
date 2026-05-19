import tkinter as tk


def check_password_strength(password):

    score = 0

    if len(password) >= 8:
        score += 1

    if any(c.isupper() for c in password):
        score += 1

    if any(c.islower() for c in password):
        score += 1

    if any(c.isdigit() for c in password):
        score += 1

    if any(not c.isalnum() for c in password):
        score += 1

    return score


def ask_password(
    root,
    APP_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT,
    ACCENT_TEXT
):

    win = tk.Toplevel(root)

    win.title("Password")
    win.geometry("350x180")
    win.configure(bg=APP_BG)

    win.grab_set()

    result = {"password": None}

    tk.Label(
        win,
        text="Enter Password",
        bg=APP_BG,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 11)
    ).pack(pady=10)

    password_var = tk.StringVar()

    entry = tk.Entry(
        win,
        textvariable=password_var,
        show="*",
        width=30
    )

    entry.pack(pady=5)

    strength_label = tk.Label(
        win,
        text="Strength: ",
        bg=APP_BG,
        fg=TEXT_SECONDARY
    )

    strength_label.pack(pady=5)

    def update_strength(*args):

        pwd = password_var.get()

        score = check_password_strength(pwd)

        if score <= 2:

            strength_label.config(
                text="Strength: Weak",
                fg="red"
            )

        elif score <= 4:

            strength_label.config(
                text="Strength: Medium",
                fg="orange"
            )

        else:

            strength_label.config(
                text="Strength: Strong",
                fg="green"
            )

    password_var.trace_add(
        "write",
        update_strength
    )

    def submit():

        result["password"] = password_var.get()

        win.destroy()

    tk.Button(
        win,
        text="OK",
        bg=ACCENT,
        fg=ACCENT_TEXT,
        command=submit
    ).pack(pady=10)

    entry.focus()

    root.wait_window(win)

    return result["password"]