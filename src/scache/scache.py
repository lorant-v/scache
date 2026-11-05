#!/usr/bin/env python3
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from enum import IntEnum
from functools import cached_property
from pathlib import Path
from typing import (
  Any,
  Protocol,
  Self,
  get_args,
  get_origin,
  get_type_hints,
)

PROG = "scache"
DEFAULT_OUTPUT_PATH = ".chezmoidata/scache.json"
DEFAULT_OUTPUT_FORMAT = "json"
DEFAULT_PROVIDER = "bitwarden"

logger = logging.getLogger(PROG)


def configure_logging(*, verbose: bool) -> None:
  logging.basicConfig(
    format=("{asctime} - {levelname} - {message}" if verbose else "{message}"),
    style="{",
    level=logging.DEBUG if verbose else logging.INFO,
    stream=sys.stderr,
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

  for fld in fields(cls):
    name = fld.name

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


def run_command(
  *command: str, check: bool = True, **kwargs: Any
) -> subprocess.CompletedProcess:
  return subprocess.run(command, check=check, text=True, encoding="utf-8", **kwargs)


def default_manifest_path() -> Path:
  """$XDG_CONFIG_HOME/scache/manifest.json, or ~/.config/scache/manifest.json"""
  config_home = os.environ.get("XDG_CONFIG_HOME")
  base = Path(config_home) if config_home else Path.home() / ".config"
  return base / "scache" / "manifest.json"


def first_set(*values):
  return next(value for value in values if value is not None)


def get_path(document: Mapping[str, object], path: str):
  """Read a dotted path out of a nested mapping."""
  node = document
  for key in path.split("."):
    if not isinstance(node, Mapping) or key not in node:
      raise ScacheError(f"Path {path} not found in document {document}")
    node = node[key]
  return node


def set_path(document: dict[str, object], path: str, value: object):
  """Write a value into a nested mapping at a dotted path.
  For an out of "secrets.app.password", the result is:
  {
    "secrets": {
      "app": {
        "password": "the fetched value"
      }
    }
  }
  """
  keys = path.split(".")
  if not path or any(not part for part in keys):
    raise ScacheError(f"Invalid output path: {path!r}")

  node = document
  for key in keys[:-1]:
    # Get key if exists, else create and get
    child = node.setdefault(key, {})
    if not isinstance(child, dict):
      raise ScacheError(f"Conflicting output paths near: {path!r}")
    node = child

  leaf = keys[-1]
  if leaf in node:
    raise ScacheError(f"Duplicate output path: {path}")
  node[leaf] = value


class ExitCode(IntEnum):
  """Process exit codes."""

  OK = 0
  ERROR = 1
  USAGE = 2  # argparse default
  DIFF = 3  # diff found changes


class ScacheError(Exception):
  """An expected, user-facing failure."""


@dataclass(frozen=True)
class UserSecret:
  ref: str  # provider-specific location, e.g. "uuid#login.password"
  out: str  # dot path into the cache, e.g. "secrets.app.password"
  provider: str | None = None  # secret provider name, e.g. "bitwarden"


@dataclass(frozen=True)
class UserOutput:
  path: str | None = None
  format: str | None = None


@dataclass(frozen=True)
class UserManifest:
  secrets: list[UserSecret]
  output: UserOutput = field(default_factory=UserOutput)
  default_provider: str | None = None

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
      return dict_to_dataclass(cls, data)
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
      raise ScacheError(f"Invalid manifest: {exc}") from exc


@dataclass(frozen=True)
class Secret:
  ref: str
  out: str
  provider: str


@dataclass(frozen=True)
class Output:
  path: str
  format: str


@dataclass(frozen=True)
class Manifest:
  secrets: tuple[Secret, ...]
  output: Output

  @classmethod
  def from_user_manifest(cls, manifest: UserManifest) -> Self:
    return cls(
      secrets=tuple(
        Secret(
          ref=secret.ref,
          out=secret.out,
          provider=(
            first_set(secret.provider, manifest.default_provider, DEFAULT_PROVIDER)
          ),
        )
        for secret in manifest.secrets
      ),
      output=Output(
        path=first_set(manifest.output.path, DEFAULT_OUTPUT_PATH),
        format=first_set(manifest.output.format, DEFAULT_OUTPUT_FORMAT),
      ),
    )


# Providers
class Provider(Protocol):
  name: str

  def is_available(self) -> bool: ...

  def fetch_all(self, secrets: Sequence[Secret]) -> Mapping[Secret, object]: ...


class BitwardenProvider:
  name = "bitwarden"

  def __init__(
    self,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = run_command,
    which: Callable[[str], str | None] = shutil.which,
  ):
    self._run = run
    self._which = which

  def split_bitwarden_ref(self, ref: str) -> tuple[str, str]:
    """Split '<item>#<dot-path>' into (item, path)"""
    item, sep, path = ref.partition("#")
    if not item or not sep or not path:
      raise ScacheError(f"Invalid Bitwarden ref {ref!r}; expected '<item>#<dot-path>'")
    return item, path

  def is_available(self) -> bool:
    return self._which("bw") is not None

  def fetch_all(self, secrets: Sequence[Secret]) -> Mapping[Secret, object]:
    return {secret: self._fetch_single(secret) for secret in secrets}

  def _fetch_single(self, secret: Secret) -> object:
    item, path = self.split_bitwarden_ref(secret.ref)
    result = self._run("bw", "get", "item", item, "--raw", stdout=subprocess.PIPE)
    try:
      payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
      raise ScacheError(f"Invalid Bitwardem item response: {item}") from exc
    return get_path(payload, path)


PROVIDERS: dict[str, Callable[..., Provider]] = {
  provider.name: provider for provider in (BitwardenProvider,)
}


def get_provider(
  name: str,
  *,
  run: Callable[..., subprocess.CompletedProcess[str]] = run_command,
  which: Callable[[str], str | None] = shutil.which,
) -> Provider:
  try:
    factory = PROVIDERS[name]
  except KeyError as exc:
    raise ScacheError(f"Unknown provider: {name}") from exc
  return factory(run=run, which=which)


class Writer(Protocol):
  name: str

  def render(self, document: Mapping[str, object]) -> str: ...

  def parse(self, text: str) -> dict[str, object]: ...


class JsonWriter:
  name = "json"

  def render(self, document: Mapping[str, object]) -> str:
    return json.dumps(document, indent=2) + "\n"

  def parse(self, text: str) -> dict[str, object]:
    return json.loads(text)


WRITERS: dict[str, Callable[..., Writer]] = {
  writer.name: writer for writer in (JsonWriter,)
}


def get_writer(
  name: str,
) -> Writer:
  try:
    factory = WRITERS[name]
  except KeyError as exc:
    raise ScacheError(f"Unknown writer: {name}") from exc
  return factory()


class Cache:
  """The generated data file in the chezmoi source."""

  def __init__(self, path: Path, writer: Writer) -> None:
    self.path = path
    self._writer = writer

  def read(self) -> dict[str, object]:
    if not self.path.exists():
      return {}
    try:
      return self._writer.parse(self.path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
      raise ScacheError(f"Cannot read cache: {self.path}") from exc

  def write(self, document: Mapping[str, object]):
    self.path.parent.mkdir(parents=True, exist_ok=True)
    text = self._writer.render(document)
    self.path.write_text(text)


def render_cache(
  manifest: Manifest, secrets: Mapping[Secret, object]
) -> dict[str, object]:
  document: dict[str, object] = {}

  for secret in manifest.secrets:
    if secret not in secrets:
      raise ScacheError(f"No fetched value for output path: {secret.out!r}")

    value = secrets[secret]
    set_path(document, secret.out, value)

  return document


def flatten(document: Mapping[str, object], prefix="") -> dict[str, object]:
  """Flatten a nested mapping into dotted keys
  For an document like
  {
    "secrets": {
      "app": {
        "password": "the fetched value"
      }
    }
  }
  the output is
  {
    "secrets.app.password": "the fetched value"
  }
  """
  flat: dict[str, object] = {}
  for key, value in document.items():
    path = f"{prefix}{key}"
    if isinstance(value, Mapping):
      flat.update(flatten(value, path + "."))
    else:
      flat[path] = value

  return flat


class SecretsCacheManager:
  def __init__(
    self,
    *,
    manifest: Manifest,
    providers: Mapping[str, Provider],
    writer: Writer,
    run: Callable[..., subprocess.CompletedProcess[str]] = run_command,
    which: Callable[[str], str | None] = shutil.which,
  ):
    self._manifest = manifest
    self._providers = providers
    self._writer = writer
    self._run = run
    self._which = which

  def install(self):
    self._require_environment()
    cache = self._cache()
    self._require_gitignored(cache.path, "cache")
    secrets = self._fetch_secrets()
    cache.write(render_cache(self._manifest, secrets))
    return cache.path

  def diff(self) -> dict[str, tuple[object | None, object | None]]:
    self._require_environment()
    cache = self._cache()
    current = flatten(cache.read())

    secrets = self._fetch_secrets()
    desired = flatten(render_cache(self._manifest, secrets))

    return {
      key: (current.get(key), desired.get(key))
      for key in desired.keys() | current.keys()
    }

  def _cache(self) -> Cache:
    return Cache(self._source_dir / self._manifest.output.path, self._writer)

  @cached_property
  def _source_dir(self) -> Path:
    result = self._run("chezmoi", "source-path", stdout=subprocess.PIPE)
    return Path(result.stdout.strip())

  def _require_environment(self) -> None:
    for dependency in ("chezmoi", "git"):
      if self._which(dependency) is None:
        raise ScacheError(f"Missing dependency: {dependency}")
    for provider in self._providers.values():
      if not provider.is_available():
        raise ScacheError(f"Missing dependency: {provider.name}")

  def _require_gitignored(self, path: Path, description: str) -> None:
    try:
      relative = path.relative_to(self._source_dir)
    except ValueError as exc:
      raise ScacheError(f"{description} is outside the chezmoi source: {path}") from exc

    result = self._run(
      "git",
      "-C",
      str(self._source_dir),
      "check-ignore",
      "-q",
      "--",
      relative.as_posix(),
      check=False,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
    )

    if result.returncode != 0:
      raise ScacheError(f"{description} must be gitignored and untracked: {path}")

  def _group_secrets(self) -> dict[str, list[Secret]]:
    grouped: dict[str, list[Secret]] = {}

    for secret in self._manifest.secrets:
      grouped.setdefault(secret.provider, []).append(secret)

    return grouped

  def _fetch_secrets(self) -> dict[Secret, object]:
    secrets_values = {}
    secrets_grouped = self._group_secrets()

    # Fetch by provider
    for provider_name, secrets in secrets_grouped.items():
      provider = self._providers[provider_name]
      secrets_values.update(provider.fetch_all(secrets))

    return secrets_values


def marker(entry: tuple[object | None, object | None]) -> str:
  current, desired = entry
  if current == desired:
    return "="
  elif current is None:
    return "+"
  elif desired is None:
    return "-"
  return "~"


class SecretsCLI:
  def __init__(self, prog: str = PROG) -> None:
    self.prog = prog
    self.parser = self.build_parser()

  def build_parser(self) -> argparse.ArgumentParser:
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

    parser.add_argument("-m", "--manifest", type=Path, help="Manifest path")

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

  def load_user_manifest(self, path: Path | None) -> UserManifest:
    return UserManifest.from_path(path if path is not None else default_manifest_path())

  def build_manager(self, manifest: Manifest) -> SecretsCacheManager:
    provider_names = {
      secret.provider for secret in manifest.secrets if secret.provider is not None
    }
    providers = {name: get_provider(name) for name in provider_names}
    writer = get_writer(manifest.output.format)
    return SecretsCacheManager(
      manifest=manifest,
      providers=providers,
      writer=writer,
    )

  def run(self, argv: list[str] | None = None) -> int:
    args = self.parse_args(argv)
    configure_logging(verbose=args.verbose)
    try:
      user_manifest = self.load_user_manifest(args.manifest)
      manifest = Manifest.from_user_manifest(user_manifest)
      manager = self.build_manager(manifest)
      return int(args.func(args, manager))
    except ScacheError as exc:
      logger.error("%s", exc, exc_info=args.verbose)
      return int(ExitCode.ERROR)

  # commands
  def cmd_install(self, args: argparse.Namespace, manager: SecretsCacheManager):
    cache_path = manager.install()
    logger.info(f"Cache installed at {cache_path}. Run chezmoi apply.")
    return 0

  def cmd_diff(self, args: argparse.Namespace, manager: SecretsCacheManager):
    entries = manager.diff()
    changed = [key for key, entry in entries.items() if entry[0] != entry[1]]

    if args.all:
      for key in sorted(entries):
        print(f"{marker(entries[key])} {key}", file=sys.stdout)
    else:
      for key in sorted(changed):
        print(key, file=sys.stdout)

    if changed:
      logger.info(f"Cache is out of date. Run {self.prog} install.")
      return int(ExitCode.DIFF)
    logger.info("Cache is up to date.")
    return int(ExitCode.OK)


def main(argv: list[str] | None = None) -> int:
  try:
    return SecretsCLI().run(argv if argv is not None else sys.argv[1:])
  except KeyboardInterrupt:
    return 130


if __name__ == "__main__":
  raise SystemExit(main())
