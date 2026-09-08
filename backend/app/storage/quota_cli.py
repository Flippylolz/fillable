"""Quota operator interface. Container execution is the privileged boundary."""

import argparse
import json

from sqlalchemy.exc import SQLAlchemyError

from app.errors import AppError
from app.storage import quotas
from app.storage.service import StorageError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage Fillable storage allocations")
    commands = parser.add_subparsers(dest="command", required=True)
    default = commands.add_parser("default")
    default.add_argument("--bytes", type=int, required=True)
    override = commands.add_parser("override")
    override.add_argument("--login", "--email", dest="login", required=True)
    override.add_argument("--bytes", type=int, required=True)
    for name in ("inherit", "show"):
        command = commands.add_parser(name)
        command.add_argument("--login", "--email", dest="login", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "default":
            result = quotas.set_default(args.bytes)
        else:
            owner = quotas.owner_for_login(args.login)
            if args.command == "show":
                state = quotas.usage(owner)
            else:
                state = quotas.set_override(
                    owner, args.bytes if args.command == "override" else None
                )
            result = state.model_dump()
        print(json.dumps(result))
        return 0
    except (AppError, StorageError, SQLAlchemyError, ValueError):
        print(json.dumps({"error": "quota_command_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
