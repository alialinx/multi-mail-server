import os

from .config import SIEVE_DIR


def script_path(email):
    local, domain = email.split("@", 1)
    return os.path.join(SIEVE_DIR, domain, f"{local}.sieve")


def escape(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def write_vacation(email, subject, text):
    path = script_path(email)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    script = (
        'require ["vacation"];\n\n'
        "vacation\n"
        "  :days 1\n"
        f'  :subject "{escape(subject)}"\n'
        f'  "{escape(text)}";\n'
    )
    with open(path, "w") as f:
        f.write(script)


def remove(email):
    path = script_path(email)
    if os.path.exists(path):
        os.remove(path)
