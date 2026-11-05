# scache
Fetch selected Bitwarden secrets into a local chezmoi cache.

Writes a generated cache (`.chezmoidata/secrets.yaml` in the chezmoi source) of secrets
that chezmoi can read as data.

## Requirements

- Python 3.11+
- `bw` (Bitwarden CLI), authenticated with your account
- `chezmoi`
- `git`

## Manifest
A manifest tells `scache` which secrets to fetch and where to put them in the generated cache. 

By default, `scache` looks for `scache/manifest.json` inside `$XDG_CONFIG_HOME`. If that environment variable is unset, it looks for `.config/scache/manifest.json` in your home directory. To use a different file, pass its path with `--manifest`:

```sh
scache --manifest path/to/manifest.json install
```

### Example manifest
```json
{
  "default_provider": "bitwarden",
  "secrets": [
      {
        "ref": "<item-id>#login.password",
        "out": "secrets.example.password"
      },
      {
        "ref": "<item-id>#login.password",
        "out": "secrets.example.password",
        "provider": "another_provider"
      }
  ],
  "output": {
    "path": ".chezmoidata/scache.json",
    "format": "json"
  }
}
```
Replace `<item-id>` with the Bitwarden item ID. The `ref` format is `<item-id>#<field-path>`, and `out` is a dot-separated path in the cache. `default_provider` applies to secrets that don’t specify their own provider. The `output` section is optional.

**Supported providers**
- bitwarden

**Supported output formats** 
- json

## Usage

```sh
bw login           # log in to bitwarden if you are not already logged in
export BW_SESSION="$(bw unlock --raw)"
scache install     # fetch secrets and write the cache
chezmoi apply      # apply templates that use the caches
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

## Acknowledgements
The approach is inspired by [Mike Casberg's article on managing dotfile secrets with chezmoi](https://www.mikekasberg.com/blog/2026/01/31/dotfiles-secrets-in-chezmoi.html).
