import pytest
from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError

from scripts.render_templates import Resources, ResourceSpec, Values, deep_merge, render_template

TEMPLATE_DIR = "templates"


@pytest.fixture
def jinja_env():
    return Environment(loader=FileSystemLoader(TEMPLATE_DIR))


@pytest.fixture
def base_values():
    return dict(
        app_name="test-app",
        env="test",
        image_repo="ghcr.io/test/app",
        image_tag="v1.0.0",
        port=8080,
        resources=Resources(
            limits=ResourceSpec(cpu="500m", memory="512Mi"),
            requests=ResourceSpec(cpu="200m", memory="256Mi"),
        ),
    )


# --- deep_merge ---

def test_deep_merge_simple():
    assert deep_merge({"a": 1, "b": 2}, {"b": 3, "c": 4}) == {"a": 1, "b": 3, "c": 4}


def test_deep_merge_nested():
    base = {"resources": {"limits": {"cpu": "500m"}, "requests": {"cpu": "200m"}}}
    override = {"resources": {"limits": {"cpu": "1000m"}}}
    result = deep_merge(base, override)
    assert result["resources"]["limits"]["cpu"] == "1000m"
    assert result["resources"]["requests"]["cpu"] == "200m"


def test_deep_merge_does_not_mutate_base():
    base = {"a": {"b": 1}}
    deep_merge(base, {"a": {"b": 2}})
    assert base["a"]["b"] == 1


# --- Values validation ---

def test_values_valid(base_values):
    v = Values(**base_values)
    assert v.app_name == "test-app"
    assert v.replicas == 2
    assert v.namespace == "default"


def test_values_proxy_missing_connection(base_values):
    base_values["enable_proxy"] = True
    with pytest.raises(ValidationError, match="db_instance_connection_name"):
        Values(**base_values)


def test_values_proxy_missing_resources(base_values):
    base_values["enable_proxy"] = True
    base_values["db_instance_connection_name"] = "project:region:instance"
    with pytest.raises(ValidationError, match="proxy_resources"):
        Values(**base_values)


def test_values_proxy_valid(base_values):
    base_values["enable_proxy"] = True
    base_values["db_instance_connection_name"] = "project:region:instance"
    base_values["proxy_resources"] = Resources(
        limits=ResourceSpec(cpu="100m", memory="128Mi"),
        requests=ResourceSpec(cpu="50m", memory="64Mi"),
    )
    v = Values(**base_values)
    assert v.enable_proxy is True


# --- render_template ---

def test_render_replicas(base_values, jinja_env):
    rendered = render_template("deployment.yaml.j2", Values(**base_values), jinja_env)
    assert "replicas: 2" in rendered


def test_render_image(base_values, jinja_env):
    rendered = render_template("deployment.yaml.j2", Values(**base_values), jinja_env)
    assert "ghcr.io/test/app:v1.0.0" in rendered


def test_render_env_vars(base_values, jinja_env):
    base_values["env_vars"] = {"LOG_LEVEL": "debug"}
    rendered = render_template("deployment.yaml.j2", Values(**base_values), jinja_env)
    assert "LOG_LEVEL" in rendered
    assert "debug" in rendered


def test_render_no_proxy_by_default(base_values, jinja_env):
    rendered = render_template("deployment.yaml.j2", Values(**base_values), jinja_env)
    assert "cloud-sql-proxy" not in rendered


def test_render_proxy_sidecar(base_values, jinja_env):
    base_values["enable_proxy"] = True
    base_values["db_instance_connection_name"] = "project:region:instance"
    base_values["proxy_resources"] = Resources(
        limits=ResourceSpec(cpu="100m", memory="128Mi"),
        requests=ResourceSpec(cpu="50m", memory="64Mi"),
    )
    rendered = render_template("deployment.yaml.j2", Values(**base_values), jinja_env)
    assert "cloud-sql-proxy" in rendered
    assert "project:region:instance" in rendered
