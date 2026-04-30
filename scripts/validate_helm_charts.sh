#!/usr/bin/env bash
set -euo pipefail

failed=0

for chart in charts/*/; do
  [ -f "${chart}Chart.yaml" ] || continue

  echo "Linting ${chart}..."
  if ! helm lint "${chart}"; then
    failed=1
  fi

  for values_file in manifests/*/helm-values.yaml; do
    [ -f "${values_file}" ] || continue
    env=$(basename "$(dirname "${values_file}")")
    echo "Validating ${chart} (${env})..."
    if ! helm template "${chart}" -f "${values_file}" | kubeconform -strict -summary -; then
      failed=1
    fi
  done
done

exit $failed
