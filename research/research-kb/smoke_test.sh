#!/usr/bin/env bash
# End-to-end smoke test for research KB ingest + search.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="${ROOT}/kb_index.sqlite"
PY="${PYTHON:-python3}"

echo "== ingest =="
"${PY}" "${ROOT}/ingest.py" --root "${ROOT}" --db "${DB}"

TOTAL="$("${PY}" -c "import sqlite3; print(sqlite3.connect('${DB}').execute('SELECT COUNT(*) FROM documents').fetchone()[0])")"
echo "document count: ${TOTAL}"
if [[ "${TOTAL}" -lt 1 ]]; then
  echo "FAIL: empty index" >&2
  exit 1
fi

echo "== search: volatility =="
OUT="$("${PY}" "${ROOT}/search.py" --root "${ROOT}" --db "${DB}" volatility --limit 3)"
echo "${OUT}"
echo "${OUT}" | grep -q '\.md' || { echo "FAIL: no path in hits" >&2; exit 1; }
echo "${OUT}" | grep -q 'cite:' || { echo "FAIL: no citation path" >&2; exit 1; }

echo "== search: HYPOTHESES (json) =="
JSON="$("${PY}" "${ROOT}/search.py" --root "${ROOT}" --db "${DB}" HYPOTHESES --limit 1 --json)"
echo "${JSON}"
echo "${JSON}" | grep -q '"path"' || { echo "FAIL: json missing path" >&2; exit 1; }

echo "== embed stub =="
"${PY}" -c "from embed_stub import get_embedder; assert get_embedder().embed_text('x') == ()" 2>/dev/null || \
  "${PY}" -c "import sys; sys.path.insert(0, '${ROOT}'); from embed_stub import get_embedder; assert get_embedder().embed_text('x') == ()"

echo "PASS smoke_test (indexed ${TOTAL} documents)"
