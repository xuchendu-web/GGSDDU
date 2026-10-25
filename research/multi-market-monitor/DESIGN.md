# Multi-Market Monitor — Design Language

Prototype aesthetic aligned with the ETF research site burn (`style.css` lineage): **clean premium finance**, not terminal chrome, not HENG-style dense grids.

## Principles

1. **Readable first** — 16px body, generous line height; numbers tabular where possible.
2. **Calm surface** — `#f7f7f8` canvas, white cards, `#e5e7eb` hairline borders, 8–10px radius.
3. **One accent** — `#2563eb` for links, focus, live pulse; avoid rainbow panels.
4. **Market semantics** — A-share uses **红涨绿跌**; HK/US panels label locale and use **绿涨红跌** in those tables only (labeled in UI).
5. **Prototype honesty** — Persistent mock banner; connection badge (Live mock / Reconnecting).

## Layout

```
┌─ Sticky header: title · market session chips · mock badge · WS status ─┐
├─ KPI strip: connected markets · tick rate · last update ───────────────┤
├─ Three columns (stack on mobile) ──────────────────────────────────────┤
│  Indices (grouped A / HK / US) │ Movers stub │ Alerts feed              │
└─ Footer: disclaimer · no trading ──────────────────────────────────────┘
```

## Typography

- UI: `-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`
- Numbers: `font-variant-numeric: tabular-nums`
- Panel titles: 13px uppercase tracking, `#6b7280`
- Index levels: 22–26px semibold `#111`

## Motion

- Price flash: 400ms background tint on change (up/down).
- New alert: subtle slide-in; no infinite animations except live dot (2s pulse).

## Color tokens

| Token        | Value     | Use              |
|-------------|-----------|------------------|
| `--bg`      | `#f7f7f8` | Page             |
| `--card`    | `#ffffff` | Panels           |
| `--border`  | `#e5e7eb` | Borders          |
| `--text`    | `#1f2937` | Body             |
| `--muted`   | `#6b7280` | Labels           |
| `--accent`  | `#2563eb` | Links, live      |
| `--up-cn`   | `#b91c1c` | A-share up       |
| `--down-cn` | `#15803d` | A-share down     |
| `--up-us`   | `#15803d` | HK/US up         |
| `--down-us` | `#b91c1c` | HK/US down       |
| `--warn`    | `#92400e` | Mock banner bg   |

## Out of scope (by design)

- Real broker APIs, auth, order entry, production deploy.
- Charting beyond sparkline placeholders (future live wire).
