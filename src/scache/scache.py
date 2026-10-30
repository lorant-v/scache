import argparse
import logging
import sys
from enum import IntEnum

PROG = "scache"
logger = logging.getLogger(PROG)


class ExitCode(IntEnum):
    """Process exit codes."""

    OK = 0
    ERROR = 1
    USAGE = 2  # argparse default
    DIFF = 3  # diff found changes


class SecretsManagerError(Exception):
    """An expected, user-facing failure."""


class SecretsManager:
    def install(self):
        pass

    def diff(self):
        pass


class SecretsCLI:
    def __init__(self, manager: SecretsManager, prog: str = PROG) -> None:
        self.manager = manager
        self.prog = prog
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog=self.prog, description="Fetch selected secrets into local cache."
        )

        sub = parser.add_subparsers(title="command", dest="command", required=True)

        p_add = sub.add_parser(
            "install", help="Fetch secrets and write the local cache."
        )
        p_add.set_defaults(func=self.cmd_install)

        p_diff = sub.add_parser(
            "diff", help="Fetch secrets and compare against the local cache."
        )
        p_diff.add_argument(
            "--all", "-a", action="store_true", help="Include unchanged secrets."
        )
        p_diff.set_defaults(func=self.cmd_diff)

        return parser

    def parse_args(self, argv: list[str] | None = None) -> argparse.Namespace:
        return self.parser.parse_args(argv)

    def run(self, argv: list[str] | None = None) -> int:
        args = self.parse_args(argv)

        try:
            return int(args.func(args))
        except SecretsManagerError as exc:
            logger.error("%s", exc)
            return int(ExitCode.ERROR)

    # commands
    def cmd_install(self, args):
        cache_path = self.manager.install()
        logger.info(f"Cache installed at {cache_path}; run chezmoi apply")
        return 0

    def cmd_diff(self, args):
        logger.info("Comparing cache")

        if self.manager.diff():
            return 1

        return 0


def main(argv: list[str] | None = None) -> int:
    cli = SecretsCLI(SecretsManager())
    try:
        return cli.run(argv if argv is not None else sys.argv[1:])
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
