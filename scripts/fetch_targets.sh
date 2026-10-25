#!/usr/bin/env bash
# Clone the target repos at pinned commits so evaluation results are reproducible.
set -euo pipefail

mkdir -p targets

fetch() {
  local name=$1 url=$2 sha=$3
  if [ ! -d "targets/$name" ]; then
    git clone --quiet "$url" "targets/$name"
  fi
  git -C "targets/$name" fetch --quiet origin "$sha"
  git -C "targets/$name" checkout --quiet "$sha"
  echo "$name @ $sha"
}

# main target
fetch insurance-claims \
  https://github.com/aws-samples/serverless-eda-insurance-claims-processing.git \
  ccabee3ead4b7de7fd815d1b13ed0197d851519e

# stretch target
if [ "${1:-}" = "--stretch" ]; then
  fetch genu \
    https://github.com/aws-samples/generative-ai-use-cases.git \
    076537388dcc0a02c7e87f3f41bc5ee8618a564b
fi
