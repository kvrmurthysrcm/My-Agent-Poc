#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible entry point retained for local documentation and older
# Jenkins replays. New pipeline runs use sonar-service.sh directly.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$script_dir/sonar-service.sh" library
