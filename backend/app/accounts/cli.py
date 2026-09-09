"""Operator commands. Passwords arrive only through private stdin or a TTY."""

import argparse
import getpass
import sys

from pydantic import ValidationError

from app.accounts.schema import AccountInput
from app.accounts.service import provision, reset_password
from app.errors import AppError


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage local Fillable accounts")
    parser.add_argument("action", choices=["provision", "reset-password"])
    parser.add_argument("--login", "--email", dest="login", required=True)
    parser.add_argument("--display-name", default="")
    parser.add_argument("--role", choices=["user", "admin"], default="user")
    parser.add_argument("--language", choices=["uk", "en"], default="uk")
    parser.add_argument("--password-stdin", action="store_true")
    options = parser.parse_args()
    try:
        if options.password_stdin:
            password = sys.stdin.read(4097).removesuffix("\n")
        else:
            password = getpass.getpass("Password: ")
            if getpass.getpass("Confirm password: ") != password:
                raise ValueError("password_mismatch")
        if options.action == "provision":
            account = AccountInput(
                login=options.login,
                display_name=options.display_name,
                role=options.role,
                ui_language=options.language,
            )
            provision(account, password)
        else:
            reset_password(options.login, password)
    except (ValueError, ValidationError, AppError) as error:
        code: str
        if isinstance(error, AppError):
            code = error.detail.code
        elif isinstance(error, ValidationError):
            code = "invalid_input"
        else:
            # Credential ValueErrors carry fixed codes such as invalid_password.
            code = str(error) or "invalid_input"
        print(code, file=sys.stderr)
        return 1
    print("completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
