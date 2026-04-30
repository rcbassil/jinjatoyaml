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
uv run scripts/render_templates.py
```

Rendered manifests are written to `manifests/<env>/`.

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
  render_templates.py
tests/
  test_render.py
```
