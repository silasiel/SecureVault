import time

failed_attempts = {}
locked_folders = {}


def record_failed_attempt(
    folder,
    log_action,
    logs_dir
):
    failed_attempts[folder] = (
        failed_attempts.get(folder, 0) + 1
    )

    attempts = failed_attempts[folder]

    log_action(
        logs_dir,
        "FAILED_UNLOCK",
        f"{folder} ({attempts} attempts)"
    )

    if attempts >= 3:
        locked_folders[folder] = time.time() + 30

        log_action(
            logs_dir,
            "VAULT_LOCKED",
            folder
        )

    return attempts


def reset_failed_attempts(folder):
    failed_attempts[folder] = 0


def is_folder_locked(folder):
    if folder not in locked_folders:
        return False, 0

    unlock_time = locked_folders[folder]

    remaining = int(unlock_time - time.time())

    if remaining <= 0:
        del locked_folders[folder]
        failed_attempts[folder] = 0

        return False, 0

    return True, remaining