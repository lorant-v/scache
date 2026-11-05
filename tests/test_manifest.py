import json

from scache import Manifest
from scache.scache import (
  DEFAULT_OUTPUT_FORMAT,
  DEFAULT_OUTPUT_PATH,
  DEFAULT_PROVIDER,
  Secret,
  UserManifest,
)


def test_parses_secrets_with_defaults():
  data = {
    "secrets": [
      {"ref": "uuid-1#notes", "out": "secrets.ssh.id_ed25519"},
      {"ref": "uuid-2#login.password", "out": "secrets.app.password"},
    ],
  }

  user_manifest = UserManifest.from_json(json.dumps(data))
  manifest = Manifest.from_user_manifest(user_manifest)

  assert (
    Secret(
      ref="uuid-1#notes",
      out="secrets.ssh.id_ed25519",
      provider=DEFAULT_PROVIDER,
    )
    in manifest.secrets
  )
  assert (
    Secret(
      ref="uuid-2#login.password",
      out="secrets.app.password",
      provider=DEFAULT_PROVIDER,
    )
    in manifest.secrets
  )
  assert manifest.output.format == DEFAULT_OUTPUT_FORMAT
  assert manifest.output.path == DEFAULT_OUTPUT_PATH


def test_parses_secrets_with_default_provider():
  default_provider = "1password"
  data = {
    "default_provider": default_provider,
    "secrets": [
      {"ref": "uuid-1#notes", "out": "secrets.ssh.id_ed25519"},
      {"ref": "uuid-2#login.password", "out": "secrets.app.password"},
    ],
  }

  user_manifest = UserManifest.from_json(json.dumps(data))
  manifest = Manifest.from_user_manifest(user_manifest)

  assert (
    Secret(
      ref="uuid-1#notes",
      out="secrets.ssh.id_ed25519",
      provider=default_provider,
    )
    in manifest.secrets
  )
  assert (
    Secret(
      ref="uuid-2#login.password",
      out="secrets.app.password",
      provider=default_provider,
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

  user_manifest = UserManifest.from_json(json.dumps(data))
  manifest = Manifest.from_user_manifest(user_manifest)

  assert (
    Secret(
      ref="uuid-1#notes",
      out="secrets.ssh.id_ed25519",
      provider="bitwarden",
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

  user_manifest = UserManifest.from_json(json.dumps(data))
  manifest = Manifest.from_user_manifest(user_manifest)

  assert (
    Secret(
      ref="uuid-1#notes",
      out="secrets.ssh.id_ed25519",
      provider="bitwarden",
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
