#!/usr/bin/env bash
# Index in-repo research/*.md plus optional local roots from ingest_roots.local.txt
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
ANCHOR="${REPO}/research"
DB="${HERE}/kb_index.sqlite"
PY="${PYTHON:-python3}"

ARGS=(--anchor "${ANCHOR}" --db "${DB}")
LOCAL="${HERE}/ingest_roots.local.txt"
if [[ -f "${LOCAL}" ]]; then
  ARGS+=(--paths-file "${LOCAL}")
fi

exec "${PY}" "${HERE}/ingest.py" "${ARGS[@]}" "$@"
