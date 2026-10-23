#!/usr/bin/env bash
set -euo pipefail
migration_dir="$(cd "$(dirname "$0")/.." && pwd)"
bash "$migration_dir/arkts/base/build.sh"
bash "$migration_dir/arkts/final/build.sh"

