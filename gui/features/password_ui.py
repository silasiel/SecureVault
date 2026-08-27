import tkinter as tk
from tkinter import messagebox


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


def prompt_password(
    root,
    APP_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT,
    ACCENT_TEXT,
    title="Password",
    prompt="Enter Password",
    show_strength=False,
    confirm=False,
    confirm_prompt="Confirm Password"
):

    win = tk.Toplevel(root)

    win.title(title)
    height = 180
    if show_strength:
        height += 40
    if confirm:
        height += 70

    win.geometry(f"360x{height}")
    win.configure(bg=APP_BG)

    win.grab_set()
    win.transient(root)

    result = {"password": None}

    tk.Label(
        win,
        text=prompt,
        bg=APP_BG,
        fg=TEXT_PRIMARY,
        font=("Segoe UI", 11)
    ).pack(pady=10)

    password_var = tk.StringVar()
    confirm_var = tk.StringVar()

    entry = tk.Entry(
        win,
        textvariable=password_var,
        show="*",
        width=30
    )

    entry.pack(pady=5)

    confirm_entry = None

    strength_label = None

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

    if show_strength:
        strength_label = tk.Label(
            win,
            text="Strength: ",
            bg=APP_BG,
            fg=TEXT_SECONDARY
        )

        strength_label.pack(pady=5)
        password_var.trace_add(
            "write",
            update_strength
        )

    if confirm:
        tk.Label(
            win,
            text=confirm_prompt,
            bg=APP_BG,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 11)
        ).pack(pady=(8, 0))

        confirm_entry = tk.Entry(
            win,
            textvariable=confirm_var,
            show="*",
            width=30
        )

        confirm_entry.pack(pady=5)

    def submit():

        password = password_var.get()

        if not password:
            messagebox.showerror(
                "Password",
                "Password cannot be empty."
            )
            return

        if confirm and password != confirm_var.get():
            messagebox.showerror(
                "Password",
                "Passwords do not match."
            )
            return

        result["password"] = password

        win.destroy()

    tk.Button(
        win,
        text="OK",
        bg=ACCENT,
        fg=ACCENT_TEXT,
        command=submit
    ).pack(pady=10)

    entry.focus()

    if confirm_entry is not None:
        confirm_entry.focus_set()

    root.wait_window(win)

    return result["password"]


def setup_master_password_dialog(
    root,
    APP_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT,
    ACCENT_TEXT
):
    return prompt_password(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT,
        title="Create Master Password",
        prompt="Create a master password for this vault:",
        show_strength=True,
        confirm=True,
        confirm_prompt="Confirm master password:"
    )


def login_master_password_dialog(
    root,
    APP_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT,
    ACCENT_TEXT
):
    return prompt_password(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT,
        title="Unlock Vault",
        prompt="Enter your master password:"
    )


def verify_master_password_dialog(
    root,
    APP_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT,
    ACCENT_TEXT,
    title="Verify Master Password",
    prompt="Re-enter your master password:"
):
    return prompt_password(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT,
        title=title,
        prompt=prompt
    )


def ask_password(
    root,
    APP_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT,
    ACCENT_TEXT,
    title="Password",
    prompt="Enter Password",
    show_strength=False
):
    return prompt_password(
        root,
        APP_BG,
        TEXT_PRIMARY,
        TEXT_SECONDARY,
        ACCENT,
        ACCENT_TEXT,
        title=title,
        prompt=prompt,
        show_strength=show_strength
    )