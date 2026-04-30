#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, model_validator

TEMPLATE_DIR = Path("templates")
OUTPUT_DIR = Path("manifests")
VALUES_DIR = Path("values")


class ResourceSpec(BaseModel):
    cpu: str
    memory: str


class Resources(BaseModel):
    limits: ResourceSpec
    requests: ResourceSpec


class Values(BaseModel):
    app_name: str
    namespace: str = "default"
    env: str
    image_repo: str
    image_tag: str
    image_pull_policy: str = "IfNotPresent"
    replicas: int = 2
    port: int
    resources: Resources
    enable_proxy: bool = False
    db_instance_connection_name: str | None = None
    proxy_resources: Resources | None = None
    env_vars: dict[str, str] = {}

    @model_validator(mode="after")
    def validate_proxy(self) -> Values:
        if self.enable_proxy:
            if not self.db_instance_connection_name:
                raise ValueError("db_instance_connection_name required when enable_proxy is true")
            if not self.proxy_resources:
                raise ValueError("proxy_resources required when enable_proxy is true")
        return self


def deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def render_template(template_name: str, values: Values, jinja_env: Environment) -> str:
    return jinja_env.get_template(template_name).render(**values.model_dump())


def load_values(env_name: str, base: dict) -> Values:
    env_file = VALUES_DIR / f"{env_name}.yaml"
    merged = deep_merge(base, yaml.safe_load(env_file.read_text()))
    return Values(**merged)


def main() -> None:
    base = yaml.safe_load((VALUES_DIR / "base.yaml").read_text())
    jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env_files = sorted(f for f in VALUES_DIR.glob("*.yaml") if f.stem != "base")

    for env_file in env_files:
        env_name = env_file.stem
        values = load_values(env_name, base)
        out_dir = OUTPUT_DIR / env_name
        out_dir.mkdir(parents=True, exist_ok=True)

        for template_path in TEMPLATE_DIR.glob("*.j2"):
            output_path = out_dir / template_path.stem
            rendered = render_template(template_path.name, values, jinja_env)
            output_path.write_text(rendered + "\n")
            subprocess.run(["git", "add", str(output_path)], check=True)
            print(f"Rendered {template_path} -> {output_path}")

    print("K8s manifests rendered successfully!")


if __name__ == "__main__":
    main()
