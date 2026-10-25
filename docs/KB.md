# Research notes knowledge base (local FTS5)

Markdown notes under `research/research-kb/` are indexed locally with SQLite FTS5. No cloud upload; content comes only from files on disk.

## Prerequisites

- Python 3.10+ (stdlib only: `sqlite3`, no pip packages)

## Build / refresh index

From the repository root:

```bash
python3 research/research-kb/ingest.py
```

Options:

| Flag | Meaning |
|------|---------|
| `--root PATH` | Directory to scan for `*.md` (default: `research/research-kb/`) |
| `--db PATH` | SQLite file (default: `<root>/kb_index.sqlite`) |
| `--force` | Re-read every file even if unchanged |

Output prints document counts and the index path. Exit code `2` if the index is empty.

## Search (CLI)

```bash
python3 research/research-kb/search.py volatility managed --limit 5
python3 research/research-kb/search.py "time series momentum"
python3 research/research-kb/search.py HYPOTHESES --json
```

- Terms are combined with **AND** unless you use quoted phrases.
- Each hit includes **path**, **title**, BM25 **score**, a **snippet** (match highlighted as `**` in text mode), and an absolute **cite** path.
- `--json` emits one JSON object per hit (includes `cite`).
- Exit code `2` when there are no matches.

## Optional embeddings (stub)

`embed_stub.py` defines a `NoOpEmbedder` and `get_embedder("noop")` for a future vector sidecar. Ingest/search do not call it today; swap in a real embedder later without changing the FTS workflow.

## Smoke test

```bash
bash research/research-kb/smoke_test.sh
```

Runs ingest, checks document count, and runs sample queries.

## Sample corpus

The bundled sample is the extracted `kb-sample` tarball: volatility-managed / TSMOM literature notes, week-42 prep, hypotheses, and judging logs (23 Markdown files). Re-run `ingest.py` after adding or editing notes.

## Why FTS5 instead of ripgrep alone

- Ranked hits (BM25) instead of flat line matches
- Snippets with context around the match
- Stable **relative path citations** for Q&A-style lookup
- Single `kb_index.sqlite` you can copy or back up with the notes

For raw regex or cross-repo search, keep using `rg`; use this index when you want ranked note retrieval with paths.
