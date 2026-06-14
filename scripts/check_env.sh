#!/usr/bin/env bash
set -euo pipefail

PROJECT_ENV="research-py312"
MAMBA="${MAMBA:-/mnt/e/WSL/micromamba/bin/micromamba}"

echo "project=NSFG_Reproductive_LifeCourse_SSL_20260601"
echo "project_env=$PROJECT_ENV"
echo "pwd=$(pwd)"

if [[ ! -x "$MAMBA" ]]; then
  echo "Missing micromamba: $MAMBA" >&2
  exit 2
fi

if [[ "$PROJECT_ENV" == "none" ]]; then
  echo "No shared environment selected."
  exit 0
fi

if ! "$MAMBA" env list | awk '{print $1}' | grep -Fxq "$PROJECT_ENV"; then
  echo "Environment not created yet: $PROJECT_ENV"
  echo "Create it with:"
  echo "  /mnt/e/Reserch/_env/scripts/create_env_from_spec.sh $PROJECT_ENV"
  exit 3
fi

ENV_PREFIX="$("$MAMBA" env list | awk -v env="$PROJECT_ENV" '$1 == env {print $NF}')"

if [[ -x "$ENV_PREFIX/bin/python" ]]; then
  "$ENV_PREFIX/bin/python" --version
else
  echo "Python is not installed inside $PROJECT_ENV."
fi

if [[ -x "$ENV_PREFIX/bin/Rscript" ]]; then
  "$ENV_PREFIX/bin/Rscript" --version
else
  echo "Rscript is not installed inside $PROJECT_ENV."
fi

echo "Environment check complete."
