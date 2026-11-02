# scache
Fetch selected Bitwarden secrets into a local chezmoi cache.

Writes a generated cache (`.chezmoidata/secrets.yaml` in the chezmoi source) of secrets
that chezmoi can read as data.

Approach inspired by [Mike Casberg](https://www.mikekasberg.com/blog/2026/01/31/dotfiles-secrets-in-chezmoi.html).

## Requirements

- Python 3.11+
- `bw` (Bitwarden CLI), `chezmoi`, and `git`

## Usage

```sh
scache install     # fetch secrets and write the cache
scache diff        # compare remote secrets against the local cache
scache diff --all  # include unchanged secrets
```

## Development
```sh
uv sync            # create the environment
uv run ruff check  # lint
uv run ruff format # format
uv run pytest      # tests
uv run ty check    # types
```