"""Teacher credential storage and provisioning."""

import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path

TEACHERS_FILE = Path(__file__).parent / "teachers.json"
ITERATIONS = 600_000


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS
    ).hex()


def authenticate(username, password):
    with TEACHERS_FILE.open(encoding="utf-8") as file:
        teachers = json.load(file)
    if not isinstance(teachers, dict):
        raise ValueError("Teacher credentials must be a JSON object")
    record = teachers.get(username)
    if record is None:
        return False
    return hmac.compare_digest(password_hash(password, record["salt"]), record["hash"])


def main():
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        sys.exit("Usage: python src/teacher_auth.py USERNAME")
    username = sys.argv[1]
    password = getpass.getpass("Teacher password: ")
    if not password or password != getpass.getpass("Confirm password: "):
        sys.exit("Passwords must be nonempty and match.")
    if TEACHERS_FILE.exists():
        with TEACHERS_FILE.open(encoding="utf-8") as file:
            teachers = json.load(file)
        if not isinstance(teachers, dict):
            sys.exit("Teacher credentials must be a JSON object.")
    else:
        teachers = {}
    salt = secrets.token_hex(16)
    teachers[username] = {"salt": salt, "hash": password_hash(password, salt)}
    with open(
        TEACHERS_FILE, "w", encoding="utf-8",
        opener=lambda path, flags: os.open(path, flags, 0o600),
    ) as file:
        os.fchmod(file.fileno(), 0o600)
        json.dump(teachers, file, indent=2)
        file.write("\n")
    print(f"Credentials saved for {username}. Restart the server to revoke existing sessions.")


if __name__ == "__main__":
    main()
