import argparse
import json
import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import IntEnum
from pathlib import Path
from typing import Self, get_args, get_origin, get_type_hints

PROG = "scache"
DEFAULT_OUTPUT_PATH = ".chezmoidata/scache.json"
DEFAULT_OUTPUT_FORMAT = "json"
DEFAULT_PROVIDER = "bitwarden"

logger = logging.getLogger(PROG)


class ExitCode(IntEnum):
  """Process exit codes."""

  OK = 0
  ERROR = 1
  USAGE = 2  # argparse default
  DIFF = 3  # diff found changes


class ScacheError(Exception):
  """An expected, user-facing failure."""


# Domain
@dataclass
class Secret:
  ref: str  # provider-specific location, e.g. "uuid#login.password"
  out: str  # dot path into the cache, e.g. "secrets.app.password"
  provider: str | None = None  # secret provider name, e.g. "bitwarden"


@dataclass(frozen=True)
class Output:
  path: str = DEFAULT_OUTPUT_PATH
  format: str = DEFAULT_OUTPUT_FORMAT


@dataclass(frozen=True)
class Manifest:
  secrets: list[Secret]
  output: Output = Output()
  default_provider: str = DEFAULT_PROVIDER

  @classmethod
  def from_path(cls, path: Path) -> Self:
    try:
      text = path.read_text(encoding="utf-8")
    except OSError as exc:
      raise ScacheError(f"Cannot read manifest: {path}") from exc
    return cls.from_json(text)

  @classmethod
  def from_json(cls, text: str) -> Self:
    try:
      data = json.loads(text)
      if not isinstance(data, Mapping):
        raise ScacheError("manifest must be a JSON object")

      manifest: Self = dict_to_dataclass(cls, data)
      manifest._normalize()

      return manifest
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
      raise ScacheError(f"Invalid manifest: {exc}") from exc

  def _normalize(self):
    for secret in self.secrets:
      secret.provider = (
        self.default_provider if secret.provider is None else secret.provider
      )


def dict_to_dataclass(cls, data):
  """
  Recursively deserialize a dictionary into a dataclass instance.

  Args:
    cls: The dataclass type to instantiate
    data: Dictionary containing the values used to construct the dataclass instance

  Returns:
    Instance of `cls`, with nested dataclasses recursively instantiated

  """
  if not is_dataclass(cls):
    return data

  hints = get_type_hints(cls)
  kwargs = {}

  for field in fields(cls):
    name = field.name

    if name not in data:
      continue

    value = data[name]
    field_type = hints[name]

    field_type_origin = get_origin(field_type)
    field_type_args = get_args(field_type)

    if field_type_origin is list:
      value = [dict_to_dataclass(field_type_args[0], item) for item in value]
    elif is_dataclass(field_type):
      value = dict_to_dataclass(field_type, value)

    kwargs[name] = value

  return cls(**kwargs)


# App
class SecretsCacheManager:
  def install(self):
    pass

  def diff(self):
    pass


class SecretsCLI:
  def __init__(self, manager: SecretsCacheManager, prog: str = PROG) -> None:
    self.manager = manager
    self.prog = prog
    self.parser = self._build_parser()

  def _build_parser(self) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
      prog=self.prog, description="Fetch selected secrets into local cache."
    )

    parser.add_argument(
      "-v",
      "--verbose",
      action="store_true",
      default=False,
      help="show detailed information",
    )

    cmds = parser.add_subparsers(title="command", dest="command", required=True)

    cmd_add = cmds.add_parser(
      "install", help="Fetch secrets and write the local cache."
    )
    cmd_add.set_defaults(func=self.cmd_install)

    cmd_diff = cmds.add_parser(
      "diff", help="Fetch secrets and compare against the local cache."
    )
    cmd_diff.add_argument(
      "--all", "-a", action="store_true", help="Include unchanged secrets."
    )
    cmd_diff.set_defaults(func=self.cmd_diff)

    return parser

  def parse_args(self, argv: list[str] | None = None) -> argparse.Namespace:
    return self.parser.parse_args(argv)

  def run(self, argv: list[str] | None = None) -> int:
    args = self.parse_args(argv)
    configure_logging(verbose=args.verbose)
    try:
      return int(args.func(args))
    except ScacheError as exc:
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


def configure_logging(*, verbose: bool) -> None:
  logging.basicConfig(
    format="{asctime} - {levelname} - {message}",
    style="{",
    level=logging.DEBUG if verbose else logging.WARNING,
    stream=sys.stderr,
  )


def main(argv: list[str] | None = None) -> int:
  cli = SecretsCLI(SecretsCacheManager())
  try:
    return cli.run(argv if argv is not None else sys.argv[1:])
  except KeyboardInterrupt:
    return 130


if __name__ == "__main__":
  raise SystemExit(main())
