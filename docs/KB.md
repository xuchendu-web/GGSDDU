# Research notes knowledge base (local FTS5)

Markdown under the repository `research/` tree (and optional local folders) is indexed with SQLite FTS5. No cloud upload; content comes only from files on disk.

## Prerequisites

- Python 3.10+ (stdlib only: `sqlite3`, no pip packages)

## Build / refresh index

**Recommended (whole repo `research/` tree):**

```bash
bash research/research-kb/ingest_workspace.sh
```

Equivalent:

```bash
python3 research/research-kb/ingest.py --anchor research --db research/research-kb/kb_index.sqlite
```

Indexed paths are stored relative to `research/` (for example `research-kb/00-索引.md`). Re-run ingest after adding or editing notes anywhere under `research/`.

### CLI options (`ingest.py`)

| Flag | Meaning |
|------|---------|
| `--anchor PATH` | Recursively index all `*.md` under this directory (default: `<repo>/research` when present) |
| `--root PATH` | Alias for `--anchor` |
| `--extra-root LABEL:PATH` | Additional directory (repeatable). `PATH` may be absolute or repo-relative |
| `--paths-file PATH` | File listing extra roots (see example below) |
| `--no-anchor-scan` | Only index `--extra-root` / paths-file entries |
| `--db PATH` | SQLite file (default: `research/research-kb/kb_index.sqlite`) |
| `--force` | Re-read every file even if unchanged |

`ingest_workspace.sh` passes `--anchor research` and, if present, `research/research-kb/ingest_roots.local.txt`.

### Local paths outside the repo

1. Copy `research/research-kb/ingest_roots.local.txt.example` to `ingest_roots.local.txt` (gitignored).
2. Add one root per line — bare path, or `label|/absolute/path`, or `label:/absolute/path`.
3. Run `bash research/research-kb/ingest_workspace.sh`.

Example `ingest_roots.local.txt`:

```text
# ~/Documents/research-notes
kimi-notes|/Users/you/Kimi/notes
```

Documents from extra roots appear as `label/relative/path.md` in search results; `cite:` resolves to the file on disk.

Exit code `2` if the index is empty after ingest.

## Search (CLI)

```bash
python3 research/research-kb/search.py volatility managed --limit 5
python3 research/research-kb/search.py "time series momentum"
python3 research/research-kb/search.py HYPOTHESES --json
```

- Terms are combined with **AND** unless you use quoted phrases.
- Each hit includes **path**, **title**, BM25 **score**, a **snippet** (match highlighted as `**` in text mode), and an absolute **cite** path (uses per-document `source_root` when set).
- `--json` emits one JSON object per hit (includes `cite`).
- `--db` points at `kb_index.sqlite` (default: next to the scripts).
- Exit code `2` when there are no matches.

## Optional embeddings (stub)

`embed_stub.py` defines a `NoOpEmbedder` and `get_embedder("noop")` for a future vector sidecar. Ingest/search do not call it today; swap in a real embedder later without changing the FTS workflow.

## Smoke test

```bash
bash research/research-kb/smoke_test.sh
```

Runs workspace ingest, checks document count and `research-kb/` path prefix, and runs sample queries.

## Sample corpus

The bundled sample is the extracted `kb-sample` tarball under `research/research-kb/`: volatility-managed / TSMOM literature notes, week-42 prep, hypotheses, and judging logs (23 Markdown files). Adding `research/<other-dir>/*.md` in the repo is picked up automatically on the next ingest.

## Why FTS5 instead of ripgrep alone

- Ranked hits (BM25) instead of flat line matches
- Snippets with context around the match
- Stable **path citations** for Q&A-style lookup
- Single `kb_index.sqlite` you can copy or back up with the notes

For raw regex or cross-repo search, keep using `rg`; use this index when you want ranked note retrieval with paths.
