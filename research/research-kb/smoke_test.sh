#!/usr/bin/env bash
# End-to-end smoke test for research KB ingest + search (+ large stub corpus).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="${ROOT}/kb_index.sqlite"
PY="${PYTHON:-python3}"
STUB_DIR="${ROOT}/_corpus_stub"
STUB_DB="${ROOT}/kb_index_stub.sqlite"

echo "== ingest (sample notes) =="
"${PY}" "${ROOT}/cli.py" ingest --root "${ROOT}" --db "${DB}" --rebuild-fts --force

TOTAL="$("${PY}" -c "import sqlite3; print(sqlite3.connect('${DB}').execute('SELECT COUNT(*) FROM documents').fetchone()[0])")"
CHUNKS="$("${PY}" -c "import sqlite3; print(sqlite3.connect('${DB}').execute('SELECT COUNT(*) FROM chunks').fetchone()[0])")"
echo "document count: ${TOTAL} chunks: ${CHUNKS}"
if [[ "${TOTAL}" -lt 1 ]]; then
  echo "FAIL: empty index" >&2
  exit 1
fi
if [[ "${CHUNKS}" -lt "${TOTAL}" ]]; then
  echo "FAIL: expected at least one chunk per document" >&2
  exit 1
fi

echo "== search: volatility (chunk mode) =="
OUT="$("${PY}" "${ROOT}/search.py" --root "${ROOT}" --db "${DB}" volatility --limit 3)"
echo "${OUT}"
echo "${OUT}" | grep -q '\.md' || { echo "FAIL: no path in hits" >&2; exit 1; }
echo "${OUT}" | grep -q 'cite:' || { echo "FAIL: no citation path" >&2; exit 1; }

echo "== search: HYPOTHESES (json) =="
JSON="$("${PY}" "${ROOT}/search.py" --root "${ROOT}" --db "${DB}" HYPOTHESES --limit 1 --json)"
echo "${JSON}"
echo "${JSON}" | grep -q '"path"' || { echo "FAIL: json missing path" >&2; exit 1; }

echo "== optional PDF fixture =="
if "${PY}" -c "
from pathlib import Path
import sys
sys.path.insert(0, '${ROOT}')
from kb_pipeline.extract import extract_pdf_text
p = Path('${ROOT}/fixtures/minimal.pdf')
t = extract_pdf_text(p)
assert t and 'FIXTURE_PDF_TOKEN' in t
print('pdf extract ok')
"; then
  echo "PDF path wired (fixtures/minimal.pdf)"
else
  echo "SKIP pdf extract (install pypdf or poppler pdftotext for PDF indexing)"
fi

echo "== large corpus stub ingest =="
rm -rf "${STUB_DIR}"
"${PY}" "${ROOT}/fixtures/gen_corpus_stub.py" --out "${STUB_DIR}" --count 500 --nested 10
STUB_START=$(date +%s)
"${PY}" "${ROOT}/cli.py" ingest --root "${STUB_DIR}" --db "${STUB_DB}" --rebuild-fts
STUB_END=$(date +%s)
STUB_DOCS="$("${PY}" -c "import sqlite3; print(sqlite3.connect('${STUB_DB}').execute('SELECT COUNT(*) FROM documents').fetchone()[0])")"
STUB_CHUNKS="$("${PY}" -c "import sqlite3; print(sqlite3.connect('${STUB_DB}').execute('SELECT COUNT(*) FROM chunks').fetchone()[0])")"
echo "stub corpus: documents=${STUB_DOCS} chunks=${STUB_CHUNKS} elapsed=$((STUB_END - STUB_START))s"
[[ "${STUB_DOCS}" -eq 500 ]] || { echo "FAIL: stub document count" >&2; exit 1; }
STUB_HIT="$("${PY}" "${ROOT}/search.py" --root "${STUB_DIR}" --db "${STUB_DB}" CORPUS_STUB_TOKEN_X9 --limit 1 --json)"
echo "${STUB_HIT}"
echo "${STUB_HIT}" | grep -q 'stub-' || { echo "FAIL: stub search miss" >&2; exit 1; }

echo "== embed stub =="
"${PY}" -c "import sys; sys.path.insert(0, '${ROOT}'); from embed_stub import get_embedder; assert get_embedder().embed_text('x') == ()"

echo "PASS smoke_test (indexed ${TOTAL} documents, stub ${STUB_DOCS})"
