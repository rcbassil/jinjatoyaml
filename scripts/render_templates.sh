#!/usr/bin/env bash
# Dependencies: yq (mikefarah/yq v4), jinja2-cli (pip install jinja2-cli)
# Usage: ./render_templates.sh [--templates DIR] [--output DIR] [--values DIR]

set -euo pipefail

TEMPLATE_DIR=""
OUTPUT_DIR=""
VALUES_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --templates) TEMPLATE_DIR="$2"; shift 2 ;;
        --output)    OUTPUT_DIR="$2";   shift 2 ;;
        --values)    VALUES_DIR="$2";   shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

[[ -z "$TEMPLATE_DIR" ]] && { echo "ERROR: --templates is required"; exit 1; }
[[ -z "$OUTPUT_DIR" ]]   && { echo "ERROR: --output is required";    exit 1; }
[[ -z "$VALUES_DIR" ]]   && { echo "ERROR: --values is required";    exit 1; }

BASE_VALUES="$VALUES_DIR/base.yaml"

validate_proxy() {
    local merged_file="$1"
    local enable_proxy
    enable_proxy=$(yq '.enable_proxy // false' "$merged_file")

    if [[ "$enable_proxy" == "true" ]]; then
        local conn
        conn=$(yq '.db_instance_connection_name // ""' "$merged_file")
        [[ -z "$conn" ]] && { echo "ERROR: db_instance_connection_name required when enable_proxy is true"; exit 1; }

        local proxy_resources
        proxy_resources=$(yq '.proxy_resources // ""' "$merged_file")
        [[ -z "$proxy_resources" ]] && { echo "ERROR: proxy_resources required when enable_proxy is true"; exit 1; }
    fi
    return 0
}

for env_file in "$VALUES_DIR"/*.yaml; do
    env_name=$(basename "$env_file" .yaml)
    [[ "$env_name" == "base" ]] && continue

    merged_file=$(mktemp)
    trap 'rm -f "$merged_file"' EXIT

    yq eval-all 'select(fileIndex == 0) * select(fileIndex == 1)' "$BASE_VALUES" "$env_file" > "$merged_file"

    validate_proxy "$merged_file"

    out_dir="$OUTPUT_DIR/$env_name"
    mkdir -p "$out_dir"

    for template in "$TEMPLATE_DIR"/*.j2; do
        filename=$(basename "$template" .j2)
        output_path="$out_dir/$filename"
        jinja2 "$template" "$merged_file" --format=yaml --strict > "$output_path"
        git add "$output_path"
        echo "Rendered $template -> $output_path"
    done

    rm -f "$merged_file"
    trap - EXIT
done

echo "K8s manifests rendered successfully!"
