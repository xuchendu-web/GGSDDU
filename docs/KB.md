# Research notes knowledge base (local FTS5)

Markdown and PDF under the repository `research/` tree (and optional local folders via `ingest_roots.local.txt`) are indexed with SQLite FTS5 at **document** and **chunk** level. No cloud upload; content comes only from files on disk.

## Prerequisites

- Python 3.10+ (stdlib: `sqlite3`, no required pip packages)
- Optional PDF text: `pip install pypdf` **or** system `pdftotext` (poppler). Encrypted, oversized, or unreadable PDFs are skipped (message on stderr).

## Build / refresh index

**Recommended (whole `research/` tree):**

```bash
bash research/research-kb/ingest_workspace.sh
```

Equivalent:

```bash
python3 research/research-kb/cli.py ingest --anchor research --rebuild-fts
python3 research/research-kb/ingest.py --anchor research --db research/research-kb/kb_index.sqlite
```

Indexed paths are stored relative to each ingest root (for example `research-kb/00-索引.md` when the anchor is `research/`).

### CLI (`cli.py` / `ingest.py`)

| Flag | Meaning |
|------|---------|
| `--anchor PATH` | Recursively index `*.md` / `*.pdf` under this directory (default: `<repo>/research`) |
| `--root PATH` | Alias for `--anchor` |
| `--extra-root LABEL:PATH` | Additional directory (repeatable) |
| `--paths-file PATH` | File listing extra roots; also reads `ingest_roots.local.txt` if present |
| `--no-anchor-scan` | Only index `--extra-root` / paths-file entries |
| `--db PATH` | SQLite file (default: `research/research-kb/kb_index.sqlite`) |
| `--force` | Re-read every file even if unchanged |
| `--rebuild-fts` | FTS5 `rebuild` on `documents_fts` and `chunks_fts` after ingest |
| `--chunk-chars` / `--chunk-overlap` | Chunking (defaults 2400 / 200) |

```bash
python3 research/research-kb/cli.py rebuild-fts
```

Skipped under each root: `fixtures/`, `_corpus_stub/`, `kb_pipeline/`, dotfiles, and common VCS/venv dirs.

### Local paths outside the repo

1. Copy `research/research-kb/ingest_roots.local.txt.example` → `ingest_roots.local.txt` (gitignored).
2. Add one root per line (`/path`, `label|/path`, or `label:/path`).
3. Run `bash research/research-kb/ingest_workspace.sh`.

Documents from extra roots use paths like `label/relative/file.md`; search `cite:` resolves via stored `source_root`.

Exit code `2` if the index is empty after ingest.

## Search (CLI)

```bash
python3 research/research-kb/search.py volatility managed --limit 5
python3 research/research-kb/search.py "time series momentum"
python3 research/research-kb/search.py HYPOTHESES --json
python3 research/research-kb/search.py volatility --mode documents
```

- Default `--mode chunks` uses `chunks_fts` (finer snippets). `--mode documents` uses whole-note BM25.
- Terms are AND-combined unless quoted.
- Hits include **path**, **title**, optional **chunk**, **score**, **snippet**, and absolute **cite** (`source_root` when set).
- Exit code `2` when there are no matches.

## Optional embeddings (stub)

`embed_stub.py` — `NoOpEmbedder` / `get_embedder("noop")` for a future vector sidecar.

## Smoke test

```bash
bash research/research-kb/smoke_test.sh
```

Workspace ingest, chunk counts, `research-kb/` path prefix, sample queries, optional `fixtures/minimal.pdf`, **500-file** generated stub corpus (`fixtures/gen_corpus_stub.py` → `_corpus_stub/`, gitignored).

## Sample corpus

Bundled `kb-sample` notes live under `research/research-kb/` (volatility-managed / TSMOM literature, week-42 prep, hypotheses, judging logs). Any new `research/**/*.md` is picked up on the next ingest.

## Why FTS5 instead of ripgrep alone

- Ranked hits (BM25) and chunk-level snippets
- Stable path citations for Q&A-style lookup
- Single `kb_index.sqlite` beside the tooling

Use `rg` for raw regex or cross-repo search; use this index for ranked retrieval with paths.
