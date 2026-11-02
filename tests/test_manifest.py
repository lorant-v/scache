import json

from scache import Manifest
from scache.scache import (
  DEFAULT_OUTPUT_FORMAT,
  DEFAULT_OUTPUT_PATH,
  DEFAULT_PROVIDER,
  Secret,
)

VALID_WITH_OUTPUT = {
  "default_provider": "bitwarden",
  "secrets": [
    {"ref": "uuid-1#notes", "out": "secrets.ssh.id_ed25519"},
    {"ref": "uuid-2#login.password", "out": "secrets.app.password"},
  ],
  "output": {"format": "json", "destination": ".chezmoidata/secrets.json"},
}


def test_parses_secrets_with_defaults():
  data = {
    "secrets": [
      {"ref": "uuid-1#notes", "out": "secrets.ssh.id_ed25519"},
      {"ref": "uuid-2#login.password", "out": "secrets.app.password"},
    ],
  }

  manifest = Manifest.from_json(json.dumps(data))

  assert manifest.default_provider == DEFAULT_PROVIDER
  assert (
    Secret(
      ref="uuid-1#notes",
      out="secrets.ssh.id_ed25519",
      provider=manifest.default_provider,
    )
    in manifest.secrets
  )
  assert (
    Secret(
      ref="uuid-2#login.password",
      out="secrets.app.password",
      provider=manifest.default_provider,
    )
    in manifest.secrets
  )
  assert manifest.output.format == DEFAULT_OUTPUT_FORMAT
  assert manifest.output.path == DEFAULT_OUTPUT_PATH


def test_parses_secrets_with_default_provider():
  data = {
    "default_provider": "1password",
    "secrets": [
      {"ref": "uuid-1#notes", "out": "secrets.ssh.id_ed25519"},
      {"ref": "uuid-2#login.password", "out": "secrets.app.password"},
    ],
  }

  manifest = Manifest.from_json(json.dumps(data))

  assert manifest.default_provider == "1password"
  assert (
    Secret(
      ref="uuid-1#notes",
      out="secrets.ssh.id_ed25519",
      provider=manifest.default_provider,
    )
    in manifest.secrets
  )
  assert (
    Secret(
      ref="uuid-2#login.password",
      out="secrets.app.password",
      provider=manifest.default_provider,
    )
    in manifest.secrets
  )
  assert manifest.output.format == DEFAULT_OUTPUT_FORMAT
  assert manifest.output.path == DEFAULT_OUTPUT_PATH


def test_parses_secrets_with_given_provider():
  data = {
    "default_provider": "bitwarden",
    "secrets": [
      {"ref": "uuid-1#notes", "out": "secrets.ssh.id_ed25519"},
      {
        "ref": "uuid-2#login.password",
        "out": "secrets.app.password",
        "provider": "1password",
      },
    ],
  }

  manifest = Manifest.from_json(json.dumps(data))

  assert manifest.default_provider == "bitwarden"
  assert (
    Secret(
      ref="uuid-1#notes",
      out="secrets.ssh.id_ed25519",
      provider=manifest.default_provider,
    )
    in manifest.secrets
  )
  assert (
    Secret(
      ref="uuid-2#login.password",
      out="secrets.app.password",
      provider="1password",
    )
    in manifest.secrets
  )
  assert manifest.output.format == DEFAULT_OUTPUT_FORMAT
  assert manifest.output.path == DEFAULT_OUTPUT_PATH


def test_parses_secrets_with_given_output():
  data = {
    "default_provider": "bitwarden",
    "secrets": [
      {"ref": "uuid-1#notes", "out": "secrets.ssh.id_ed25519"},
      {
        "ref": "uuid-2#login.password",
        "out": "secrets.app.password",
        "provider": "1password",
      },
    ],
    "output": {"path": ".chezmoidata/scache.yaml", "format": "yaml"},
  }

  manifest = Manifest.from_json(json.dumps(data))

  assert manifest.default_provider == "bitwarden"
  assert (
    Secret(
      ref="uuid-1#notes",
      out="secrets.ssh.id_ed25519",
      provider=manifest.default_provider,
    )
    in manifest.secrets
  )
  assert (
    Secret(
      ref="uuid-2#login.password",
      out="secrets.app.password",
      provider="1password",
    )
    in manifest.secrets
  )
  assert manifest.output.format == "yaml"
  assert manifest.output.path == ".chezmoidata/scache.yaml"
