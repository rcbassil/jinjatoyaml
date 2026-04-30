# jinjatoyaml

Renders Jinja2 Kubernetes manifest templates against per-environment values files, with Pydantic schema validation and kubeconform manifest validation baked into the pre-commit pipeline.

## How it works

```
values/base.yaml  ──┐
values/nprod.yaml ──┤ deep merge ──► render_templates.py ──► manifests/nprod/deployment.yaml
values/prod.yaml  ──┘                                    └──► manifests/prod/deployment.yaml
```

On every commit, pre-commit runs two hooks in order:
1. **Render** — merges base + env values, validates with Pydantic, renders all `.j2` templates, and stages the output.
2. **Validate** — runs `kubeconform --strict` against every file in `manifests/`.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- [pre-commit](https://pre-commit.com/)
- Go (used by pre-commit to install kubeconform automatically)

## Setup

```bash
uv sync --all-groups
pre-commit install
```

## Rendering manually

```bash
uv run scripts/render_templates.py --templates DIR --output DIR --values DIR
```

| Flag | Description |
|---|---|
| `--templates` | Directory containing `.j2` template files |
| `--output` | Directory where rendered manifests are written |
| `--values` | Directory containing `base.yaml` and env override files |

Example:

```bash
uv run scripts/render_templates.py --templates templates --output manifests --values values
```

Rendered manifests are written to `<output>/<env>/`.

## Switching to the shell renderer

A shell alternative (`scripts/render_templates.sh`) is available. It uses `yq` for YAML merging and `jinja2-cli` for rendering instead of the Python stack.

**1. Install the extra dependencies:**

`jinja2-cli` is a Python package and installs the same way everywhere:

```bash
pip install jinja2-cli
```

`yq` is a binary and varies by platform:

| Platform | Command |
|---|---|
| macOS | `brew install yq` |
| Linux (Debian/Ubuntu) | `snap install yq` |
| Linux (binary) | `wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq && chmod +x /usr/local/bin/yq` |
| Windows (Chocolatey) | `choco install yq` |
| Windows (winget) | `winget install MikeFarah.yq` |

**2. Update `.pre-commit-config.yaml`:**

```yaml
- id: render-jinja-templates
  name: Render Jinja2 K8s Templates
  entry: ./scripts/render_templates.sh
  language: script
  files: \.(j2|jinja2|yaml|yml)$
  pass_filenames: false
```

Both scripts require the same flags and can be called with custom paths:

```bash
./scripts/render_templates.sh --templates templates --output manifests --values values
```

**Trade-offs vs the Python renderer:**

| | Python (`render_templates.py`) | Shell (`render_templates.sh`) |
|---|---|---|
| Dependencies | `uv` (managed) | `yq` + `jinja2-cli` (unmanaged) |
| Schema validation | Pydantic — clear errors on bad values | Basic field checks only |
| Test coverage | Full (`uv run pytest`) | None — tests only cover the Python path |

## Split-repo setup: manifests + templates here, values in a separate repo

The pre-commit hook lives in this repo alongside the templates and rendered manifests. Values are maintained in a separate repo and made available locally via a git submodule or a CI clone.

### Option 1: Plain git clone

Clone the values repo to a conventional path before running pre-commit:

```bash
git clone <values-repo-url> ext/values
```

Update `.pre-commit-config.yaml` to point at that path:

```yaml
entry: uv run scripts/render_templates.py --templates templates --output manifests --values ext/values
```

The hook works as-is — it only requires the path to exist on disk. Add `ext/values` to `.gitignore` so it isn't accidentally committed:

```bash
echo "ext/" >> .gitignore
```

Every contributor must clone the values repo manually before their first commit. A setup script makes this easy to enforce:

```bash
#!/usr/bin/env bash
# setup.sh
git clone <values-repo-url> ext/values
uv sync --all-groups
pre-commit install
```

Tradeoff: no version pin — everyone gets whatever `HEAD` of the values repo is at clone time, so two contributors can silently render against different values.

### Option 2: Git submodule

Add the values repo as a submodule:

```bash
git submodule add <values-repo-url> ext/values
```

Update `.pre-commit-config.yaml` to point at the submodule:

```yaml
entry: uv run scripts/render_templates.py --templates templates --output manifests --values ext/values
```

After cloning this repo, contributors must initialise the submodule:

```bash
git submodule update --init
```

The pre-commit hook continues to enforce rendering on every commit. Tradeoff: the submodule pins a specific commit of the values repo — updating values requires a deliberate `git submodule update` and a follow-up commit here.

### Option 3: CI pipeline

Clone the values repo in the pipeline alongside this repo, pass the path as `--values`, then commit and push the rendered manifests back:

```bash
git clone <this-repo-url>   manifests-repo
git clone <values-repo-url> values-repo

uv run manifests-repo/scripts/render_templates.py \
  --templates manifests-repo/templates \
  --values    values-repo/values \
  --output    manifests-repo/manifests

cd manifests-repo
git add manifests/
git commit -m "chore: render manifests"
git push
```

Pre-commit no longer enforces rendering on commit — the pipeline is the single source of truth. Tradeoff: rendering is decoupled from the commit workflow, so stale manifests are possible if the pipeline is skipped.

| | Plain clone | Git submodule | CI pipeline |
|---|---|---|---|
| Pre-commit enforcement | Yes | Yes | No — pipeline only |
| Contributor setup | Manual clone + convention | `git submodule update --init` | Standard clone |
| Values versioning | Unpinned — latest at clone time | Pinned to a submodule commit | Latest (or a ref you specify) |

## Adding a new environment

1. Create `values/<env>.yaml` with any overrides on top of `values/base.yaml`.
2. Run the render script — a new `manifests/<env>/` directory is created automatically.

## Adding a new template

1. Add a `.j2` file to `templates/`.
2. The render script picks it up automatically on the next run.

## Values schema

Defined as a Pydantic model in `scripts/render_templates.py`. Required fields:

| Field | Type | Default |
|---|---|---|
| `app_name` | `str` | — |
| `env` | `str` | — |
| `image_repo` | `str` | — |
| `image_tag` | `str` | — |
| `port` | `int` | — |
| `resources` | `Resources` | — |
| `namespace` | `str` | `"default"` |
| `replicas` | `int` | `2` |
| `image_pull_policy` | `str` | `"IfNotPresent"` |
| `enable_proxy` | `bool` | `false` |
| `db_instance_connection_name` | `str` | — (required if `enable_proxy: true`) |
| `proxy_resources` | `Resources` | — (required if `enable_proxy: true`) |
| `env_vars` | `dict[str, str]` | `{}` |

## Running tests

```bash
uv run pytest
```

## Project structure

```
templates/          # Jinja2 templates (.j2)
values/
  base.yaml         # Shared defaults
  nprod.yaml        # Non-prod overrides
  prod.yaml         # Prod overrides
manifests/
  nprod/            # Rendered output (committed)
  prod/
scripts/
  render_templates.py  # Python renderer (default)
  render_templates.sh  # Shell renderer (alternative, see above)
tests/
  test_render.py
```
