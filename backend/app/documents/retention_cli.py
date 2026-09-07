"""Container-operator history policy and explicit one-shot pruning."""

import argparse
import json
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.documents import retention
from app.infrastructure import database
from app.storage.service import StorageError


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Manage Fillable saved history retention"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show")
    configure = commands.add_parser("set")
    configure.add_argument(
        "--keep-latest", required=True, help="all or 1–10000; original is always kept"
    )
    prune = commands.add_parser("prune")
    prune.add_argument("--after", type=UUID)
    prune.add_argument("--batch", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            with database().connect() as connection:
                result = retention.policy(connection).model_dump()
        elif args.command == "set":
            result = retention.configure(
                None if args.keep_latest == "all" else int(args.keep_latest)
            ).model_dump()
        else:
            result = retention.prune(after=args.after, batch=args.batch)
        print(json.dumps(result))
        return int(
            any(
                item["status"]
                not in (
                    "pruned",
                    "already_deleted",
                    "protected_version",
                    "operation_in_progress",
                )
                for item in result.get("versions", [])
            )
        )
    except (StorageError, SQLAlchemyError, ValueError):
        print(json.dumps({"error": "retention_command_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
