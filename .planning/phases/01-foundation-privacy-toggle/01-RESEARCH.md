# Phase 1: Foundation & Privacy Toggle - Research

**Researched:** 2026-05-29
**Domain:** Brownfield refactor of an existing Streamlit desktop app — dependency removal, per-user path resolution (platformdirs), and a durable per-job preference plumbed through an async pipeline
**Confidence:** HIGH

## Summary

This phase is almost entirely **integration work against existing, well-understood code** — not greenfield. Three changes ship together: (1) deleting the two cloud TTS engines, (2) routing every filesystem path through a single `platformdirs`-backed resolver, and (3) adding a durable, per-page, privacy-first LLM-cleaning toggle. All three touch `diana/config.py` and the dashboard pages; only the toggle touches the pipeline.

The single most important finding for the planner: **there is no per-job cleaning flag anywhere today.** `pipeline.py` decides cleaning purely from the *global* `get_llm_config(config)` (lines 56-60). The `Job` dataclass has no `use_llm` field, and the SQLite `jobs` table has no such column. The toggle that already exists on `4_Web.py` (`st.toggle("Clean with LLM", value=True)`) is **decorative** — it never reaches the pipeline and even contradicts the privacy-first default. So PRIV-01/02/03 require a new `Job` field, a new DB column (additive migration), a pipeline branch change, and a durable per-page store — a true thin vertical slice from UI → DB → pipeline. `4_Web.py` is out of this phase's named requirements (PRIV covers Upload + News only) but its fake toggle should be reconciled so behaviour is consistent.

The second finding: `platformdirs` is **not currently installed** (`.venv` is Python 3.13.13). It is the one new runtime dependency. Latest is **4.10.0** (released 2026-05-28). `ffmpeg 8.1` is already on PATH, so the News-off digest MP3 path works today. `pytest 9.0.3` is installed but `pytest-asyncio` is **not** — this turns out not to block existing tests (they all use `asyncio.run()` directly, no `@pytest.mark.asyncio`), but Wave 0 should still add it to the env for any new async tests.

**Primary recommendation:** Add `platformdirs>=4.10.0`; introduce a `diana/paths.py` resolver built on `PlatformDirs("Diana", appauthor=False)` and make `StorageConfig`/`KokoroConfig`/`PiperConfig` defaults derive from it; add a nullable `use_llm` column to `jobs` + a `use_llm: bool | None` field on `Job`, thread it through `pipeline.py`; persist the per-page remembered toggle in a tiny `app_settings(key TEXT PK, value TEXT)` SQLite table (survives restart, UI-only, sits beside the existing DB). Delete the two cloud engine modules and their config sections; add a fallback-with-one-time-notice in the registry for stale engine names.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 — No data migration.** First run initializes a fresh per-user data dir via `platformdirs`; repo-local `./data/` is left untouched. Prior job history and downloaded models are sacrificed deliberately.
- **D-02 — Config relocates, seeded fresh.** Live config moves to the per-user config dir, seeded from defaults/example on first run. Repo-root `config.yaml` is NOT read. `config.example.yaml` stays as a template. User re-enters settings/keys via the Settings page.
- **D-03 — Single path resolver.** All paths (DB, config, models, voices, uploads, chunks, output) derive from one resolver using `platformdirs` with app name "Diana". No relative `data/...` paths anywhere.
- **D-04 — Clean break on engine removal.** `openai_tts` and `elevenlabs` removed from registry, config schema (nested config sections deleted), and all dashboard UI. No alias/shim.
- **D-05 — Stale-engine handling = fallback + one-time notice.** A saved config naming a removed engine falls back to the default engine, shows a brief one-time in-UI notice, logs a warning. Config is NOT silently auto-rewritten/healed.
- **D-06 — First-run default = OFF (privacy-first).** Before any remembered choice exists, the per-job toggle is OFF. Rule-based cleaner is the default off-path (existing `clean_text()`; its overhaul is Phase 2).
- **D-07 — Remembered choice is independent per page.** Upload and News each persist and recall their own last toggle state. State MUST survive an app restart (PRIV-03).
- **D-08 — No-provider state.** When no LLM provider is configured, the toggle is disabled with a clear explanation (PRIV-04).
- **D-09 — News with LLM OFF = single digest.** A fetch with LLM off produces ONE digest MP3 of everything fetched (all active sources): full cleaned article text concatenated, short pause/silence between articles, **no** spoken titles/headers, **no** summarization, **no** categorization. LLM ON keeps today's per-story summarized + categorized flow.
- **D-10 — Assume a non-technical end user; everything is UI-configurable.** Every setting introduced MUST be reachable/changeable through the Streamlit dashboard, never by editing `config.yaml`/files/code. File/env overrides may exist only as a dev convenience, never the sole path.

### Claude's Discretion
- Persistence mechanism for the remembered per-page toggle (config field vs. small SQLite settings row vs. prefs file) — planner's choice, provided it survives restart (PRIV-03) and is UI-only (D-10).
- Exact `platformdirs` author/app-name parameters and the internal resolver API shape.
- Article ordering within the news digest (e.g. by source, then fetch order).
- Exact wording of the one-time removed-engine notice (D-05) and the toggle-disabled explanation (D-08).

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope. (Explicitly: no rule-based cleaner overhaul [Phase 2], no native OS TTS [Phase 3], no first-class Windows / `pathlib` hardening or `.streamlit/config.toml` relocation [Phase 6].)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RETIRE-01 | ElevenLabs + OpenAI TTS removed from registry, config schema, all UI | Exact removal map below: 2 engine modules, 5 registry edits, 2 config dataclasses + `save_config` block, 3 Settings UI sections, 1 Upload `_API_ENGINES` set, `list_engines()`. No tests reference them. |
| PLAT-01 | App data in OS per-user dirs via `platformdirs`, all paths from one resolver | platformdirs 4.10.0 API verified; complete inventory of 9 hardcoded `data/` sites (config defaults + `delete_job` default arg + cosmetic kokoro error strings); resolver design + init-ordering analysis below. |
| PRIV-01 | Toggle LLM cleaning per job in Upload flow | Requires new `Job.use_llm` field + DB column + `pipeline.py` branch (currently global-only). Upload page wiring + durable read/write pattern documented. |
| PRIV-02 | Toggle LLM cleaning on News page | Same plumbing; News additionally needs the LLM-off digest assembly path (D-09). |
| PRIV-03 | Toggle remembers last choice (persisted beyond Streamlit session) | `st.session_state` proven ephemeral (lost on refresh/restart) — must use durable store. Recommended `app_settings` SQLite table; per-page keys. |
| PRIV-04 | Toggle disabled w/ explanation when no provider; News LLM-off → audio of cleaned raw text | `get_llm_config()` already returns `None` when unconfigured — the exact gate. News digest reuses scraper `RawArticle.excerpt` + `clean_text` + `chunk_text` + `merge_chunks`. |

## Project Constraints (from CLAUDE.md)

These carry the same authority as locked decisions. Plans must not contradict them:

- **Platform:** must run on Windows AND macOS — the resolver must produce correct paths on both. Use `appauthor=False` (see Pitfall 2) to avoid the doubled `Diana\Diana` path on Windows.
- **TTS local-only:** removing cloud TTS *advances* this constraint; do not reintroduce any hosted TTS.
- **Privacy:** LLM cleaning optional per job — the core of PRIV-01..04. Default OFF.
- **Local-first / offline:** core conversion must work fully offline; the LLM-off path (rule-based clean → chunk → synth → merge) must never require network.
- **No terminal / no file editing (D-10 sharpened):** every new setting reachable from the dashboard.
- **`.venv` discipline (user memory):** all python/pip/pytest run inside the project's `.venv` (`.venv/bin/python`). Verified present, Python 3.13.13.
- **UI configurability (user memory):** assume a non-technical end user; never require file/code edits for any setting.
- **Decisive config (user memory):** config-style tasks should be fast; prefer a compact toggle UI over long prose/interrogation.
- **Conventions:** snake_case modules; `Optional[T]` style is used in `models.py`/`database.py` (match it there); lazy provider imports; new DB connection per call; `%`-style logging (never f-strings in log calls); typed exceptions with f-string messages; private helpers prefixed `_`.
- **GSD enforcement:** edits must flow through a GSD workflow (informational — applies to execution, not this research).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Path resolution (DB/config/models/uploads/chunks/output) | Data/Config layer (`diana/config.py` + new `diana/paths.py`) | Entry points (`Home.py`, `run.py`) call it at startup | One resolver is the single source of truth; config dataclasses consume it; entry points only ensure dirs exist. |
| Engine enumeration & removal | TTS layer (`diana/tts/registry.py`) | Dashboard (picker reads `list_engines()`) | Registry is the single place engines are listed/constructed; UI is downstream. |
| Stale-engine fallback + notice | TTS layer (registry/config-load) → surfaced in Dashboard | — | Fallback decision belongs near engine construction/config load; the *notice* is a UI concern (one-time `st.session_state` flag + `st.warning`). |
| Per-job cleaning decision | Processing layer (`pipeline.py`) | Data layer (`Job` + `jobs` column carries the flag) | The pipeline already owns the clean/skip branch; the flag must travel with the job through the DB (worker runs on a separate thread). |
| Toggle UI + durable persistence | Dashboard (`1_Upload.py`, `3_News.py`) | Data layer (durable `app_settings` store) | UI sets the value; durable store outlives the session (Streamlit state is ephemeral). |
| News LLM-off digest assembly | News + Processing (`3_News.py` builds text; reuses `chunker`/`merger` via the job pipeline) | — | Digest is "skip summarize, concatenate cleaned article text" — a text-assembly step feeding the existing pipeline. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `platformdirs` | `>=4.10.0` | Per-user data/config/cache directories, cross-platform | The PyPA-maintained successor to `appdirs`; the de-facto standard for desktop app paths on macOS + Windows. `[VERIFIED: PyPI — 4.10.0, released 2026-05-28]` `[CITED: platformdirs.readthedocs.io/en/latest/api.html]` |
| `sqlite3` (stdlib) | — | Durable per-page toggle store + existing jobs DB | Already the app's only inter-thread channel and persistence layer; no new dependency. `[VERIFIED: codebase — diana/database.py]` |
| `pydub` | `>=0.25.1` (existing) | Concatenate digest chunks → MP3 with silence | Already used by `merge_chunks`; the digest reuses it verbatim. `[VERIFIED: codebase — diana/processing/merger.py]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-asyncio` | `>=0.23.0` (declared, NOT installed) | Async test support | Only if Wave 0 adds `@pytest.mark.asyncio` tests. Existing async coverage uses `asyncio.run()` and does not need it. `[VERIFIED: .venv probe — module absent]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `platformdirs` | hand-rolled `~/Library/...` vs `%LOCALAPPDATA%` branching | Reinvents a solved, well-tested cross-platform problem; violates "Don't Hand-Roll" and the Windows constraint. platformdirs is 22 KB, pure-Python, zero transitive deps. |
| SQLite `app_settings` table for the toggle | New field on `DianaConfig` (YAML) | YAML works and is UI-writable via `save_config()`, BUT the config singleton is loaded once at startup and the toggle changes per interaction — a DB row read each rerun is simpler and avoids rewriting the whole YAML on every toggle. Both satisfy PRIV-03/D-10; DB is recommended (see Pattern 3). |
| SQLite `app_settings` table | JSON prefs file in the config dir | A prefs file is a third persistence mechanism to manage; the DB already exists and is transactional. Avoid adding a file format. |

**Installation:**
```bash
.venv/bin/python -m pip install "platformdirs>=4.10.0"
# then add to requirements.txt and pyproject.toml [project.dependencies]
```

**Version verification:**
```bash
.venv/bin/python -m pip index versions platformdirs   # → 4.10.0 (latest), confirmed available
```
`platformdirs 4.10.0` released 2026-05-28 (one day before research date) — current. `[VERIFIED: PyPI]`

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `platformdirs` | PyPI | ~6 yrs (2.0 in 2021; lineage from `appdirs` 2010) | ~200M+/mo (top-tier; transitive dep of pip, virtualenv, black, pylint) | github.com/tox-dev/platformdirs | unavailable | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

> slopcheck could not be installed in this environment. `platformdirs` is a PyPA/`tox-dev`-maintained package, pure-Python, 22 KB wheel, zero transitive dependencies, and is a transitive dependency of pip itself — it is not a hallucination risk. The planner may treat it as `[VERIFIED: PyPI]` given its provenance, but per protocol a `checkpoint:human-verify` before first install is acceptable and cheap. No other external packages are introduced by this phase.

## Architecture Patterns

### System Architecture Diagram

```text
                          ┌─────────────────────────────────────────────┐
  app start (run.py /     │  diana/paths.py  (NEW — single resolver)     │
  Home.py)  ───────────▶  │  PlatformDirs("Diana", appauthor=False)      │
                          │  data_dir / config_dir / db / uploads /      │
                          │  chunks / output / models / voices           │
                          └───────────────┬───────────────┬─────────────┘
                                          │               │
              seeds defaults into         │               │ ensure_dir() at startup
                                          ▼               ▼
                          ┌─────────────────────────┐   ┌──────────────────────────┐
                          │ diana/config.py          │   │ per-user data dir on disk │
                          │ StorageConfig defaults   │   │ ~/Library/Application      │
                          │ now come from resolver   │   │  Support/Diana/ (macOS)    │
                          └────────────┬─────────────┘   │ %LOCALAPPDATA%\Diana\(Win) │
                                       │                 └──────────────────────────┘
   ┌───────────────────────────────────┼─────────────────────────────────────────┐
   │ Dashboard (Streamlit, main thread) │                                          │
   │  1_Upload.py / 3_News.py           │                                          │
   │   • engine picker = list_engines() │  reads/writes durable toggle             │
   │   • LLM toggle (default OFF; gated │ ───────────────┐                         │
   │     by get_llm_config()!=None)     │                ▼                         │
   │   • create_job(... use_llm=...)    │      ┌────────────────────────┐          │
   └───────────────┬────────────────────┘      │ app_settings (SQLite)  │          │
                   │ writes jobs row            │ key='upload.use_llm'   │          │
                   │ (incl. use_llm column)     │ key='news.use_llm'     │          │
                   ▼                            └────────────────────────┘          │
   ┌────────────────────────┐                                                       │
   │ jobs table (SQLite)     │   polled by                                          │
   │  + use_llm column (NEW) │ ─────────────▶  JobWorker (daemon thread, own loop)  │
   └────────────────────────┘                            │                          │
                                                          ▼                          │
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │ pipeline.process_job(job, config)                                              │
   │   decide = (job.use_llm IS NOT None ? job.use_llm : <legacy global>)           │
   │   if decide AND get_llm_config(config): text = await llm_clean_text(...)       │
   │   else:                                  text = clean_text(...)   ◀── default   │
   │   → chunk_text → synthesize (×N) → merge_chunks → MP3                           │
   └──────────────────────────────────────────────────────────────────────────────┘

   News LLM-OFF digest (D-09):  3_News.py, on fetch with toggle OFF:
     scrape all active sources → for each RawArticle: clean_text(excerpt/full)
     → concatenate with "\n\n" (pause comes from merger gap_ms) → ONE web/txt job
     → NO summarize_all_sources(), NO categories, NO spoken titles
```

### Recommended Project Structure
```
diana/
├── paths.py              # NEW — single platformdirs resolver (data_dir, config_file, db_path, etc.)
├── config.py             # MODIFIED — defaults derive from paths.py; drop OpenAITTSConfig/ElevenLabsConfig; relocate load/save
├── database.py           # MODIFIED — add `use_llm` column migration; add app_settings table + get/set helpers; fix delete_job default
├── models.py             # MODIFIED — add `use_llm: Optional[bool] = None` to Job
├── tts/
│   ├── registry.py       # MODIFIED — drop openai_tts/elevenlabs; add stale-engine fallback
│   ├── openai_tts_engine.py    # DELETE
│   └── elevenlabs_engine.py    # DELETE
├── processing/
│   └── pipeline.py       # MODIFIED — honor job.use_llm in the clean branch
└── dashboard/
    ├── Home.py           # MODIFIED — ensure dirs via resolver; drop "cloud" copy
    └── pages/
        ├── 1_Upload.py   # MODIFIED — durable LLM toggle (default OFF, gated); drop _API_ENGINES
        ├── 3_News.py     # MODIFIED — durable LLM toggle; LLM-off digest path
        ├── 4_Web.py      # MODIFIED (reconcile) — fix decorative toggle to match (out of named scope but inconsistent)
        └── 5_Settings.py # MODIFIED — delete OpenAI TTS + ElevenLabs sections; keep LLM section
run.py                    # MODIFIED — _sync_config_toml reads relocated config; (.streamlit/ path stays relative — Phase 6)
```

### Pattern 1: Single Path Resolver (`diana/paths.py`)
**What:** One module exposes every path. Config dataclass defaults call it. Nothing else constructs paths from string literals.
**When to use:** Everywhere a `data/...` literal exists today.
**Example:**
```python
# diana/paths.py  — pattern based on [CITED: platformdirs.readthedocs.io/en/latest/api.html]
from pathlib import Path
from platformdirs import PlatformDirs

# appauthor=False → on Windows yields ...\Diana (NOT ...\Diana\Diana). See Pitfall 2.
_dirs = PlatformDirs(appname="Diana", appauthor=False)

def data_dir() -> Path:
    return Path(_dirs.user_data_dir)          # macOS: ~/Library/Application Support/Diana

def config_dir() -> Path:
    return Path(_dirs.user_config_dir)        # macOS: ~/Library/Application Support/Diana

def db_path() -> Path:        return data_dir() / "diana.db"
def upload_dir() -> Path:     return data_dir() / "uploads"
def chunk_dir() -> Path:      return data_dir() / "chunks"
def output_dir() -> Path:     return data_dir() / "output"
def model_dir() -> Path:      return data_dir() / "models"
def voices_dir() -> Path:     return data_dir() / "voices"
def config_file() -> Path:    return config_dir() / "config.yaml"

def ensure_dirs() -> None:
    for d in (data_dir(), upload_dir(), chunk_dir(), output_dir(), model_dir(), voices_dir(), config_dir()):
        d.mkdir(parents=True, exist_ok=True)
```
> Note: on macOS `user_config_dir == user_data_dir` (both `~/Library/Application Support/Diana`). That is correct and expected platformdirs behaviour; do not "fix" it. On Windows they differ only by roaming, which we are not using. `[CITED: platformdirs.readthedocs.io/en/latest/api.html]`

### Pattern 2: Config defaults derive from the resolver (not module-import side effects)
**What:** `StorageConfig` / `KokoroConfig` / `PiperConfig` defaults call resolver functions via `field(default_factory=...)`, so paths are computed lazily and stay overridable from the Settings UI.
**Example:**
```python
# diana/config.py (modified) — keep str type to match existing dataclass + save_config
from diana import paths

@dataclass
class StorageConfig:
    upload_dir: str = field(default_factory=lambda: str(paths.upload_dir()))
    chunk_dir: str = field(default_factory=lambda: str(paths.chunk_dir()))
    output_dir: str = field(default_factory=lambda: str(paths.output_dir()))
    model_dir: str = field(default_factory=lambda: str(paths.model_dir()))
    database_path: str = field(default_factory=lambda: str(paths.db_path()))
```
**Why default_factory, not a literal:** a bare `str(paths.db_path())` as a class-body default evaluates at import time — acceptable here (paths are deterministic), but `default_factory` is the dataclass-idiomatic way to defer and keeps tests that patch the resolver clean. `[VERIFIED: codebase — config.py already uses field(default_factory=...) for nested dataclasses]`

**Config load/save relocation (D-02):** change the default `path` argument of `load_config`/`get_config`/`save_config` from `"config.yaml"` to `str(paths.config_file())`, and seed from `config.example.yaml` (or pure defaults) on first run. The repo-root `config.yaml` must no longer be the read target. The Settings page already calls `save_config(config)` with no path arg → it will write to the relocated file automatically once the default changes. `[VERIFIED: codebase — 5_Settings.py:280, config.py:161]`

### Pattern 3: Durable per-page toggle via a tiny SQLite settings table (RECOMMENDED)
**What:** A `key→value` table read on each rerun, written when the toggle flips. Survives restart (PRIV-03), driven only from the UI (D-10).
**When to use:** Any remembered-per-page preference. Per-page independence (D-07) = distinct keys (`upload.use_llm`, `news.use_llm`).
**Example:**
```python
# diana/database.py (additions) — follows the existing "open→exec→commit→close" pattern
def init_app_settings(db_path: str) -> None:        # call inside init_db()
    conn = _get_connection(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit(); conn.close()

def get_setting(db_path: str, key: str, default: str | None = None) -> str | None:
    conn = _get_connection(db_path)
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(db_path: str, key: str, value: str) -> None:
    conn = _get_connection(db_path)
    conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    conn.commit(); conn.close()
```
```python
# 1_Upload.py — durable, privacy-first (default OFF), gated by provider availability
from diana.database import get_setting, set_setting
from diana.llm.registry import get_llm_config

llm_available = get_llm_config(config) is not None        # PRIV-04 gate (already returns None when unconfigured)
remembered = get_setting(config.storage.database_path, "upload.use_llm", "0") == "1"   # D-06: default OFF
use_llm = st.toggle(
    "Clean with AI (LLM)",
    value=remembered and llm_available,
    disabled=not llm_available,
    help=("Sends text to your configured LLM to clean it before narration. "
          "Off = on-device rule-based cleaning, nothing leaves your machine.")
          if llm_available else
         ("Disabled — configure an LLM provider in Settings to enable AI cleaning."),  # D-08
)
if llm_available and use_llm != remembered:
    set_setting(config.storage.database_path, "upload.use_llm", "1" if use_llm else "0")
# at job creation: Job(..., use_llm=use_llm)
```
**Why DB over the config YAML:** the config is a load-once singleton; toggling on every interaction and rewriting the entire YAML each time (and re-reading via a fresh singleton) is heavier and racier than a one-row upsert. Both are valid per the decision; DB is the cleaner fit. (If the planner prefers config, that is allowed by Claude's Discretion — but then the singleton must be refreshed after `save_config`, which is currently NOT done anywhere.)

### Pattern 4: Per-job flag threaded through the pipeline
**What:** `Job` gains `use_llm: Optional[bool] = None`. `None` = "no per-job choice recorded" → preserve legacy global behaviour (back-compat for any in-flight rows). `pipeline.py` resolves the effective decision.
**Example:**
```python
# pipeline.py (modified clean branch, replacing lines 56-60)
llm_cfg = get_llm_config(config)
want_llm = job.use_llm if job.use_llm is not None else (llm_cfg is not None)  # legacy default
if want_llm and llm_cfg is not None:
    text = await llm_clean_text(text, llm_cfg)
else:
    text = clean_text(text)
```
**DB migration (additive, idempotent — matches existing migration loop at `database.py:80`):**
```python
"ALTER TABLE jobs ADD COLUMN use_llm INTEGER"   # NULL = unset; 1/0 = explicit. Add to the try/except loop.
```
`Job.__post_init__` should coerce the int column to a bool/None (the row dict comes straight from SQLite). `create_job`/`_row_to_job` must include the new column. `[VERIFIED: codebase — database.py:142,193 INSERT/UPDATE column lists]`

### Pattern 5: News LLM-OFF digest (D-09)
**What:** On fetch with the toggle OFF, skip `summarize_all_sources()` entirely. Scrape all active sources, take each `RawArticle`'s text, run it through `clean_text()`, concatenate with blank lines, create ONE job. The pipeline's `merge_chunks(gap_ms=...)` already inserts silence between chunks — that IS the "pause between articles." No spoken titles, no categories.
**Example (assembly inside `3_News.py`, LLM-off branch):**
```python
from diana.processing.cleaner import clean_text
parts: list[str] = []
for src in all_sources:                       # all active sources (D-09)
    articles, _ = scrape_source(<best url>)   # reuse existing fetch ladder
    for a in articles:
        body = clean_text(a.excerpt or a.headline)   # full cleaned text, no header line
        if body.strip():
            parts.append(body.strip())
digest_text = "\n\n".join(parts)              # blank line → chunk boundary → gap_ms silence
# write digest_text to a temp .txt, create Job(file_type="txt", use_llm=False) → existing pipeline
```
> The current LLM-ON path builds `lines` with `story.headline` + `Source:` + summary (`3_News.py:649-655`). The OFF path must NOT include those — it is plain article prose only. Article ordering is Claude's Discretion (source order then fetch order is the obvious choice). `[VERIFIED: codebase — scraper.RawArticle has .excerpt/.headline; 3_News.py existing assembly]`

### Anti-Patterns to Avoid
- **Reading the relocated config but writing the old path (or vice-versa).** Change `load_config`/`get_config`/`save_config` defaults together; verify a Settings save round-trips to the per-user file.
- **Auto-healing a stale engine name in config (violates D-05).** Fall back at construction/enumeration time and show a one-time notice; do NOT silently overwrite the saved value.
- **Relying on `st.session_state` for the remembered toggle.** It is per-tab and lost on refresh/restart — fails PRIV-03. Use the durable store; `session_state` may *cache* the value within a session but is not the source of truth.
- **Defaulting the toggle ON (as `4_Web.py` does today).** Violates D-06 privacy-first.
- **Adding a non-nullable `use_llm` DB column with a default.** Use nullable so existing/in-flight rows mean "legacy behaviour," not a forced choice.
- **Hardcoding `~/Library/...` or `%LOCALAPPDATA%`.** Use the resolver; this is the whole point of PLAT-01 and the Windows constraint.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-user app directory per OS | `if sys.platform == "darwin": ... elif "win32": ...` | `platformdirs.PlatformDirs("Diana", appauthor=False)` | Edge cases: Windows roaming vs local, `%LOCALAPPDATA%` env quirks, macOS `Application Support` spacing, version subdirs. PyPA-maintained, tested across OSes. |
| Pause between digest articles | Custom WAV silence insertion / ffmpeg concat scripting | Existing `merge_chunks(..., gap_ms=config.processing.gap_ms)` | Already inserts `AudioSegment.silent(gap_ms)` between chunks; the digest just feeds it chunk boundaries. |
| Key→value preference store | Bespoke JSON file + read/write/locking | SQLite `app_settings` table (one upsert) | DB already exists, is transactional, and is the established inter-thread channel. No new file format. |
| Text→speech-clean for the digest | New cleaning routine | Existing `clean_text()` | It's already the off-path cleaner this phase standardizes on (overhaul is Phase 2). |
| Stale-engine detection | New validation framework | `list_engines()` membership check + fallback to `config.tts.engine`/default | Single registry function already enumerates valid engines. |

**Key insight:** Every primitive this phase needs already exists in the codebase except per-user paths — and that one primitive has a single, dominant, PyPA-blessed library. The phase is wiring, not invention.

## Runtime State Inventory

> This is a brownfield refactor + rename of storage locations and a config-schema change. A grep finds files; it does not find runtime/registered state. Each category answered explicitly.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | Existing repo-local `./data/diana.db` (jobs, news_sources, news_source_feeds, news_source_groups, news_stories) and `./data/models/*.onnx`, `./data/uploads`, `./data/output`. Per **D-01 these are deliberately abandoned, not migrated.** The new per-user DB starts empty; models re-download; news sources must be re-added (or re-imported via the existing Export/Import JSON in `3_News.py`). | **None (by decision).** Optionally surface a first-run note that the library starts empty. Do NOT write migration code. |
| **Live service config** | None. Diana calls no external service that stores the path/string server-side. LLM/(removed) TTS keys live in the local config only. RSS source URLs live in the local DB (abandoned per D-01; user can re-import JSON). | None. |
| **OS-registered state** | None. No Task Scheduler / launchd / systemd / pm2 registration embeds a Diana path. Launch is `run.py` / `Diana.command` invoked directly. | None — verified: no scheduler/daemon registration in repo. |
| **Secrets / env vars** | `${OPENAI_API_KEY}`, `${ELEVENLABS_API_KEY}` referenced by `_env_substitute`. After RETIRE-01, `ELEVENLABS_API_KEY` and the OpenAI-TTS key field are no longer read (the OpenAI *LLM* key under `llm.api_key` is unaffected — different field). Env-var *names* are unchanged; this is a code/schema change, not a secret rename. | Remove the two TTS key fields from the schema + Settings UI; leave `${...}` substitution and the LLM key path intact. |
| **Build artifacts / installed packages** | `platformdirs` not installed in `.venv` → add to `requirements.txt` + `pyproject.toml` and `pip install`. No egg-info/compiled-binary staleness (editable install of `diana` via `pythonpath=["."]`; no entry-point rename). The repo-root `config.yaml` (tracked, modified per git status) becomes a non-target — leave the file, just stop reading it. | `pip install platformdirs>=4.10.0`; update both dependency manifests. |

**Canonical question — after every file is updated, what runtime state still holds an old path?** Only the *old* `./data/` tree and repo-root `config.yaml`, which D-01/D-02 intentionally orphan. Nothing is registered with the OS or a remote service. The only real install action is adding `platformdirs`.

## Common Pitfalls

### Pitfall 1: Config singleton not refreshed after a path/schema change mid-session
**What goes wrong:** `get_config()` caches `_config` at first call (`config.py:150-158`). If a plan relocates config or removes engine sections but a page already imported the old singleton, stale paths/fields linger until process restart.
**Why it happens:** Module-level singleton, set once.
**How to avoid:** All path/schema changes take effect at process start (entry points). Don't expect a running session to pick up a relocation. For the toggle, prefer the DB store specifically because it sidesteps the singleton entirely. Verify by full app restart, not just a Streamlit rerun.
**Warning signs:** Settings "Save" appears to work but paths/old engines reappear until restart.

### Pitfall 2: Windows path doubles to `Diana\Diana`
**What goes wrong:** `PlatformDirs("Diana")` with default `appauthor=None` produces `C:\Users\<u>\AppData\Local\Diana\Diana` on Windows (appauthor defaults to appname). `[CITED: platformdirs.readthedocs.io/en/latest/api.html]`
**Why it happens:** Windows convention is `<base>\<appauthor>\<appname>`; omitting appauthor defaults it to the appname.
**How to avoid:** Pass `appauthor=False` to collapse to `...\Diana`. macOS is unaffected (`~/Library/Application Support/Diana` either way).
**Warning signs:** Nested `Diana/Diana` on Windows; raised in code review or on the Windows CI runner (Phase 6) if missed now.

### Pitfall 3: `delete_job` relative default arg silently re-anchors to CWD
**What goes wrong:** `delete_job(db_path, job_id, chunk_base="data/chunks")` (`database.py:219`) has a **relative literal default**. Both Library call sites pass `chunk_base=config.storage.chunk_dir` explicitly, so the app is fine — but any new caller (or `test_database.py:103` which omits it) silently uses `./data/chunks`, leaving orphaned chunk dirs or deleting the wrong tree relative to CWD.
**Why it happens:** A leftover relative default that predates the resolver.
**How to avoid:** Change the default to `None` and resolve to `paths.chunk_dir()` inside the function when `None`. This is part of "no relative `data/...` paths remain" (PLAT-01 success criterion).
**Warning signs:** Chunk dirs not cleaned after delete; `data/chunks` created in the repo when running from the source tree.

### Pitfall 4: `kokoro` is imported eagerly at registry top-level
**What goes wrong:** `diana/tts/registry.py:3` does `from diana.tts.kokoro_engine import KokoroEngine` at module scope (NOT lazy, unlike piper/openai/elevenlabs). Importing the registry imports kokoro. After removing the cloud engines, kokoro remains the eager default — fine, but means any import-time failure surfaces app-wide.
**Why it matters here:** When deleting `openai_tts_engine.py`/`elevenlabs_engine.py`, ensure no lingering top-level import of them exists (there are none today — they're lazy inside `_get_engine_class`/`create_engine`), so deletion is clean. Just remove their three lazy branches and drop them from `list_engines()` and `_ENGINE_CLASSES` (they're not in `_ENGINE_CLASSES` anyway).
**How to avoid:** Delete the two `if engine_name == "openai_tts"/"elevenlabs"` branches in both `_get_engine_class` and `create_engine`, the `elevenlabs` special-case in `get_engine_voices`, and trim `list_engines()` to `["kokoro", "piper"]`.
**Warning signs:** `ValueError: Unknown TTS engine` only if a stale saved config still names a removed engine → that is exactly the D-05 fallback case.

### Pitfall 5: Stale saved engine name crashes the picker instead of falling back
**What goes wrong:** `1_Upload.py:37` and `5_Settings.py:51` do `list_engines().index(config.tts.engine)`. If `config.tts.engine == "elevenlabs"` (a value a pre-existing config could hold), `.index()` raises `ValueError` and the page crashes — violating success criterion #1 ("app still runs").
**Why it happens:** `.index()` assumes the saved value is still a member.
**How to avoid (D-05):** Guard every `list_engines().index(config.tts.engine)`: if the saved engine is not in `list_engines()`, fall back to the default (`"kokoro"`), set a one-time `st.session_state` notice flag, render `st.warning("OpenAI/ElevenLabs TTS were removed; using Kokoro.")`, and `logger.warning(...)`. Do not rewrite the config.
**Warning signs:** `ValueError: 'elevenlabs' is not in list` traceback on page load with an old config. (Per D-02 fresh config seeding, a brand-new install won't hit this — but the requirement explicitly wants graceful handling if it does.)

### Pitfall 6: `_API_ENGINES` audio-format branch left dangling in Upload
**What goes wrong:** `1_Upload.py:71` defines `_API_ENGINES = {"openai_tts", "elevenlabs"}` to pick `audio/mp3` vs `audio/wav` for the preview. After removal both remaining engines (kokoro, piper) output WAV, so the set is always empty and the branch is dead.
**How to avoid:** Remove `_API_ENGINES` and hardcode `audio/wav` for the preview (kokoro/piper both produce WAV). `[VERIFIED: codebase — kokoro/piper return WAV; only the deleted engines returned MP3]`
**Warning signs:** Lint/dead-code; harmless if left but should go for cleanliness under RETIRE-01 ("all UI surfaces").

### Pitfall 7: First-run ordering — resolver dirs must exist before `init_db`
**What goes wrong:** `init_db` does `Path(db_path).parent.mkdir(parents=True, exist_ok=True)` (`database.py:19`) so the DB dir is self-creating, but `Home.py:27-29` separately mkdir's upload/chunk/output/model dirs. If the resolver moves these, that loop must use resolver paths, and the worker thread (started at `Home.py:37`) begins polling the new DB immediately.
**How to avoid:** Call `paths.ensure_dirs()` once at the top of `Home.py` (and `run.py` before `_sync_config_toml` if it needs the config dir). The worker reads `config.storage.database_path`, which now points at the per-user DB — confirm the config singleton is built before the worker starts (it is: `get_config()` at `Home.py:18`, worker at `:37`). `[VERIFIED: codebase — Home.py ordering]`

## Code Examples

### Removing an engine from the registry (RETIRE-01)
```python
# diana/tts/registry.py (after) — kokoro eager, piper lazy; cloud engines gone
def list_engines() -> list[str]:
    return ["kokoro", "piper"]

def _get_engine_class(engine_name: str):
    if engine_name == "piper":
        from diana.tts.piper_engine import PiperEngine
        return PiperEngine
    cls = _ENGINE_CLASSES.get(engine_name)          # {"kokoro": KokoroEngine}
    if cls is None:
        raise ValueError(f"Unknown TTS engine: {engine_name}")
    return cls
# get_engine_voices: delete the entire `if engine_name == "elevenlabs": ...` block.
```

### Safe engine-index with fallback + one-time notice (D-05, used in Upload & Settings)
```python
# Source: pattern derived from codebase 1_Upload.py:37 / 5_Settings.py:51
engines = list_engines()
saved = config.tts.engine
if saved not in engines:
    if not st.session_state.get("_engine_removed_notified"):
        st.warning("OpenAI/ElevenLabs TTS were removed. Using Kokoro instead.")
        st.session_state["_engine_removed_notified"] = True
    logger.warning("Saved TTS engine %r no longer available; falling back to kokoro", saved)
    saved = "kokoro"
engine_name = st.selectbox("Engine", engines, index=engines.index(saved))
```

### macOS path sanity check (what the resolver yields)
```bash
# Verified locally:
.venv/bin/python -c "import os; print(os.path.expanduser('~/Library/Application Support/Diana'))"
# → /Users/tyler/Library/Application Support/Diana
```
`[VERIFIED: local probe]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `appdirs` for per-user paths | `platformdirs` (PyPA fork) | `appdirs` unmaintained since ~2020; platformdirs is the successor | Use `platformdirs`; `appdirs` is effectively deprecated. |
| Relative `data/` next to source | OS per-user data dir | This phase (PLAT-01) | Required for read-only packaged bundles (Phase 6) and on-demand downloads (Phase 4). |
| Cloud TTS (OpenAI/ElevenLabs) | Local-only engines | This phase (RETIRE-01) | Aligns with the local-first/privacy core value. |
| Global config-controlled LLM cleaning | Per-job UI toggle | This phase (PRIV-01..04) | Moves the privacy decision to point-of-use, default OFF. |

**Deprecated/outdated:**
- `appdirs`: superseded by `platformdirs`.
- `config.tts.openai_tts` / `config.tts.elevenlabs` schema sections: removed this phase.
- `4_Web.py`'s `st.toggle("Clean with LLM", value=True)`: a non-functional, default-ON toggle predating real per-job plumbing — reconcile to the durable, default-OFF pattern (even though Web is outside the named PRIV requirements, the inconsistency is user-visible).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The planner will choose the SQLite `app_settings` table for the toggle store. It is *recommended*, but Claude's Discretion allows a config field or prefs file. | Pattern 3 / Standard Stack | Low — all three satisfy PRIV-03/D-10; only the wiring differs. If config is chosen, the singleton-refresh gap (Pitfall 1) must be handled. |
| A2 | Reconciling `4_Web.py`'s decorative toggle is in scope as a consistency fix. Web is NOT in the named PRIV-01..04 requirements (those say Upload + News). | Recommended Structure / State of the Art | Low — flagged as optional. If the planner scopes it out, the inconsistent default-ON toggle simply remains until a later phase. |
| A3 | The News digest should clean each article with the *existing* `clean_text()` (Phase-2 overhaul not yet done). D-06 says the off-path uses the existing cleaner. | Pattern 5 | Low — explicitly aligned with D-06. |
| A4 | `pytest-asyncio` is not required for existing tests (all use `asyncio.run()`); Wave 0 only needs it if new async-marker tests are added. | Validation Architecture | Low — verified no `@pytest.mark.asyncio` outside one CLI test that also uses asyncio.run; existing suite runs without it. |
| A5 | platformdirs `appauthor=False` is the right call for a single-author personal app to avoid `Diana\Diana` on Windows. | Pitfall 2 | Low — documented behaviour; the alternative (an author dir) is merely cosmetic but the doubled-appname form is undesirable. |

## Open Questions

1. **Should the relocated config seed from `config.example.yaml` or pure dataclass defaults?**
   - What we know: D-02 says "seeded fresh from defaults/example." `config.example.yaml` exists as a template.
   - What's unclear: Whether the example's documented values (which may still list cloud-TTS sections) are desirable to copy, vs. starting from clean `DianaConfig()` defaults.
   - Recommendation: Seed from `DianaConfig()` defaults (post-removal schema) and write via `save_config()` so the on-disk file never contains the removed sections. Treat `config.example.yaml` as human reference only, and update it to drop the removed sections.

2. **Does `.streamlit/config.toml` need to move out of the repo this phase?**
   - What we know: `run.py:_sync_config_toml` and `5_Settings.py:_sync_streamlit_config` write `.streamlit/config.toml` relative to CWD. PLAT-01 says "no relative `data/...` paths" — `.streamlit/` is not under `data/`.
   - What's unclear: Whether it's in scope. CONTEXT.md scopes `.streamlit/config.toml` relocation to Phase 6 (packaging) implicitly ("first-class Windows / pathlib hardening … separate phases").
   - Recommendation: Leave `.streamlit/config.toml` relative this phase (it's a Streamlit launch artifact, not app data). Note it for Phase 6. Do not let it block PLAT-01.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.13.13 (`.venv`) | — |
| `platformdirs` | PLAT-01 resolver | ✗ | — (4.10.0 available on PyPI) | None needed — `pip install platformdirs>=4.10.0` |
| `ffmpeg` | MP3 encoding (digest + all output) | ✓ | 8.1 | pydub degrades without it, but it's present |
| `pytest` | Tests | ✓ | 9.0.3 | — |
| `pytest-asyncio` | Async-marker tests (not currently used) | ✗ | — (>=0.23.0 declared) | Existing tests use `asyncio.run()`; install only if Wave 0 adds markers |
| `sqlite3` | DB + settings store | ✓ | stdlib | — |

**Missing dependencies with no fallback:**
- `platformdirs` — must be installed (single `pip install`; trivial). Add to `requirements.txt` + `pyproject.toml`.

**Missing dependencies with fallback:**
- `pytest-asyncio` — not needed by the current suite; add only if new `@pytest.mark.asyncio` tests are written.

## Validation Architecture

> nyquist_validation is enabled for this project. This section maps each success criterion to an observable/testable check.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (`[tool.pytest.ini_options]` in pyproject.toml: `testpaths=["tests"]`, `pythonpath=["."]`) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/python -m pytest tests/test_config.py tests/test_database.py tests/test_pipeline.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RETIRE-01 | `list_engines()` returns only kokoro+piper; removed engines raise `ValueError` via `create_engine` | unit | `.venv/bin/python -m pytest tests/test_tts_registry.py -x` | ❌ Wave 0 (no `test_tts_registry.py` today) |
| RETIRE-01 | Saved config naming a removed engine does not crash (fallback) | unit | `.venv/bin/python -m pytest tests/test_tts_registry.py::test_stale_engine_fallback -x` | ❌ Wave 0 |
| PLAT-01 | Resolver yields per-user paths; no `data/` literal in resolved config | unit | `.venv/bin/python -m pytest tests/test_paths.py -x` | ❌ Wave 0 (new `diana/paths.py` + test) |
| PLAT-01 | `StorageConfig` defaults are absolute and under the resolver dir | unit | `.venv/bin/python -m pytest tests/test_config.py::TestStorageDefaults -x` | ⚠️ extend `test_config.py` |
| PLAT-01 | `delete_job` default `chunk_base` no longer relative | unit | `.venv/bin/python -m pytest tests/test_database.py -x` | ✅ extend existing |
| PRIV-01/02 | `Job.use_llm` round-trips through DB; pipeline honors it (True→llm path, False→clean_text) | unit | `.venv/bin/python -m pytest tests/test_pipeline.py -x` | ✅ extend (add use_llm cases to existing mocked pipeline tests) |
| PRIV-03 | `app_settings` get/set persists; survives a fresh connection | unit | `.venv/bin/python -m pytest tests/test_database.py::TestAppSettings -x` | ❌ Wave 0 (new test class) |
| PRIV-04 | When `get_llm_config()` is None, effective decision = rule-based regardless of stored toggle | unit | `.venv/bin/python -m pytest tests/test_pipeline.py::test_no_provider_forces_rule_based -x` | ❌ Wave 0 |
| PRIV-04 (News digest) | LLM-off digest concatenates cleaned article text with blank-line boundaries, no headlines/categories | unit | `.venv/bin/python -m pytest tests/test_news_digest.py -x` | ❌ Wave 0 (extract assembly into a testable pure function) |
| Success #1 ("app still runs") | App imports + key pages load with a stale-engine config | smoke (manual or import test) | `.venv/bin/python -c "import diana.dashboard.Home"` (import-level) + manual launch | partial |

### Sampling Rate
- **Per task commit:** quick run (config + database + pipeline) — sub-second, covers the riskiest units.
- **Per wave merge:** full suite `.venv/bin/python -m pytest tests/ -q`.
- **Phase gate:** full suite green + manual UI walk-through of the 4 success criteria (engine picker shows only local engines; data dir created under `~/Library/Application Support/Diana`; toggle survives a real app restart; toggle disabled with explanation when no provider; News-off produces one digest MP3) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_paths.py` — covers PLAT-01 (resolver returns absolute per-user paths; monkeypatchable)
- [ ] `tests/test_tts_registry.py` — covers RETIRE-01 (`list_engines()` membership, removed-engine `ValueError`, stale fallback)
- [ ] `tests/test_database.py::TestAppSettings` — covers PRIV-03 (get/set/upsert persistence)
- [ ] `tests/test_news_digest.py` — covers PRIV-04 digest assembly (requires extracting the concatenation into a pure helper, e.g. `build_digest_text(sources) -> str`, so it's testable without Streamlit)
- [ ] Extend `tests/test_config.py` — StorageConfig defaults are resolver-derived/absolute; round-trip to relocated path
- [ ] Extend `tests/test_pipeline.py` — `use_llm=True/False/None` decision matrix (mocked, no real LLM/TTS)
- [ ] Framework install (only if async markers introduced): `.venv/bin/python -m pip install "pytest-asyncio>=0.23.0"`
- [ ] Manual-only (justified): per-user dir actually created on disk, and toggle surviving a full process restart — these cross the Streamlit/OS boundary and are validated by the phase-gate manual walk-through, not unit tests.

## Security Domain

> security_enforcement default (absent in config) = enabled. This phase is local-single-user with no network server, so most categories are N/A — documented for completeness.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local single-user desktop app; no auth layer (per ARCHITECTURE.md). |
| V3 Session Management | no | No server sessions; Streamlit state is local. |
| V4 Access Control | no | No multi-user/authorization. |
| V5 Input Validation | yes | The relocated config path and any UI-entered paths should stay within the resolver dir; existing upload-path traversal guard in `1_Upload.py:122` must be preserved. News source/group names are rendered with `unsafe_allow_html=True` (`3_News.py:237`) — pre-existing XSS surface tracked as HARD-03 (Phase 7), do not worsen it here. |
| V6 Cryptography | no | No new crypto. LLM/(removed) TTS keys remain plaintext-or-`${ENV}` in local config (existing behaviour; Settings already warns). |

### Known Threat Patterns for {Streamlit local desktop app + filesystem refactor}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via UI-entered model/config path escaping the per-user dir | Tampering | Validate that resolved paths stay under `paths.data_dir()`/`config_dir()` (mirror the existing upload-dir `.resolve().startswith(...)` check). |
| Reading/writing outside the sandbox because a relative `data/` default re-anchors to CWD | Tampering / Info disclosure | Eliminate all relative path defaults (Pitfall 3) — directly satisfies PLAT-01. |
| Reintroducing a network egress path under the "local-only" promise | Info disclosure | RETIRE-01 removes the only cloud-TTS egress; ensure the digest/off-path performs zero network calls (rule-based clean is offline). |
| Stale-engine crash bricking the app (availability) | Denial of Service | D-05 fallback + guarded `.index()` (Pitfall 5) keeps the app running. |

## Sources

### Primary (HIGH confidence)
- Codebase (read in full this session): `diana/config.py`, `diana/tts/registry.py`, `diana/tts/base.py`, `diana/tts/openai_tts_engine.py`, `diana/tts/elevenlabs_engine.py`, `diana/database.py`, `diana/models.py`, `diana/processing/pipeline.py`, `diana/processing/llm_cleaner.py`, `diana/processing/cleaner.py`, `diana/processing/chunker.py`, `diana/processing/merger.py`, `diana/processing/worker.py`, `diana/news/summarizer.py`, `diana/news/scraper.py`, `diana/llm/registry.py`, `diana/dashboard/Home.py`, `diana/dashboard/pages/{1_Upload,3_News,4_Web,5_Settings}.py`, `run.py`, `pyproject.toml`, `requirements.txt`, `tests/{test_config,test_pipeline,test_summarizer}.py` — used for every `[VERIFIED: codebase]` claim and the removal/plumbing maps.
- `platformdirs.readthedocs.io/en/latest/api.html` — PlatformDirs constructor params, `appauthor=False` behaviour, roaming, `_dir` vs `_path`, macOS/Windows path outputs, `ensure_exists` (no auto-create by default). `[CITED]`
- PyPI `platformdirs` JSON + `pip index versions` — latest 4.10.0 (released 2026-05-28), full version list. `[VERIFIED]`
- Local environment probes — `.venv` Python 3.13.13; `platformdirs`/`pytest-asyncio` absent; `pytest 9.0.3`; `ffmpeg 8.1`; macOS data dir path; full grep of hardcoded `data/` sites and `delete_job`/engine references. `[VERIFIED]`

### Secondary (MEDIUM confidence)
- Streamlit Community + Docs on session_state lifecycle — confirms `st.session_state` is ephemeral (lost on tab close/refresh/restart), so PRIV-03 needs a durable store. Cross-checked against multiple community threads + official docs. `[CITED: docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state]`

### Tertiary (LOW confidence)
- None — all load-bearing claims verified against the codebase, the official platformdirs docs, or local probes.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — single new dep (`platformdirs`) verified current on PyPI + official API docs; everything else already in the codebase.
- Architecture / integration map: HIGH — every integration point read directly; the "no per-job flag exists" gap and the relative-default-arg bug were confirmed by grep + file reads, not assumed.
- Pitfalls: HIGH — derived from actual code lines (eager kokoro import, `_API_ENGINES`, `.index()` crash, `delete_job` default) and documented platformdirs Windows behaviour.
- Validation: MEDIUM-HIGH — framework verified; test files exist for config/database/pipeline; several new Wave-0 test files required (enumerated).

**Research date:** 2026-05-29
**Valid until:** 2026-06-28 (stable domain; platformdirs and the codebase change slowly. Re-verify platformdirs version if planning slips past ~30 days.)
