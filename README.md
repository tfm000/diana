# Diana — Text-to-Speech Document Converter <!-- v1.0.0 -->

<table>
<tr>
<td width="40%">
   <img src="diana/dashboard/static/full.png" alt="Diana" height="400">
</td>
<td valign="top" style="padding-left: 24px;">

Diana converts documents, webpages, and news into high-quality MP3 audio using local or cloud AI text-to-speech models. All core processing runs on your machine — cloud features are optional.

**Features**
- Upload PDF, EPUB, or TXT files and convert to MP3
- Select specific pages or chapters to convert
- Multiple TTS engines: **Kokoro**, **Piper** (local); **OpenAI TTS**, **ElevenLabs** (cloud, optional)
- Choose voice and speed per job; preview voices before converting
- Optional LLM text cleaning (OpenAI / Anthropic / Google Gemini) with translation support
- **News aggregator:** add sources with RSS feeds and groups, fetch and AI-summarise top stories per category, convert to audio; export/import source lists as JSON to share with others
- **Web URL to Audio:** paste any URL and Diana scrapes, cleans, and converts it to an MP3 job
- Track jobs and play/download audio in the Library
- Configurable theme (dark, light, or auto-detect)
- Local-first — no internet required for core TTS features

**Quick Start**
1. Install prerequisites (Python 3.10+, ffmpeg)
2. Run `./setup.sh` (macOS/Linux) or `setup.bat` (Windows)
3. Double-click `Diana.command` (macOS) or `Diana.bat` (Windows)
4. Open [http://localhost:8501](http://localhost:8501)

</td>
</tr>
</table>

## Prerequisites

- **Python 3.10+** (3.10, 3.11, 3.12, 3.13 all supported)
- **ffmpeg** (required for MP3 encoding)

### Install ffmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
```bash
choco install ffmpeg
```

Or download from https://ffmpeg.org/download.html and add to your PATH.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tfm000/diana.git
   cd diana
   ```

2. **Run the setup script** (creates venv, installs deps, downloads all models, copies config):

   macOS / Linux:
   ```bash
   ./setup.sh
   ```

   Windows:
   ```bat
   setup.bat
   ```

   This creates a `Diana.command` (macOS) or `Diana.bat` (Windows) launcher you can double-click to start Diana.

<details>
<summary>Manual installation (if you prefer not to use the setup script)</summary>

1. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```

2. **Activate the virtual environment:**

   macOS / Linux:
   ```bash
   source .venv/bin/activate
   ```

   Windows:
   ```bash
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Download the Kokoro TTS model files** (~340 MB total):
   ```bash
   # macOS / Linux
   curl -L -o data/models/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
   curl -L -o data/models/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
   ```

   Windows (PowerShell):
   ```powershell
   mkdir data\models -Force
   Invoke-WebRequest -Uri "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx" -OutFile "data\models\kokoro-v1.0.onnx"
   Invoke-WebRequest -Uri "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" -OutFile "data\models\voices-v1.0.bin"
   ```

5. **Download the Piper TTS model files** (~60 MB):
   ```bash
   curl -L -o data/models/en_US-lessac-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
   curl -L -o data/models/en_US-lessac-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
   ```

6. **Copy the example config:**
   ```bash
   cp config.example.yaml config.yaml
   ```

</details>

## Usage

**Start Diana:**
```bash
python run.py
```

Open http://localhost:8501 in your browser.

### Home

The landing page displays Diana's artwork and quick links to all pages.

### Upload

Navigate to the **Upload** page to convert a document to audio.

1. **Choose a file** — drag-and-drop or browse for a PDF, EPUB, or TXT file (up to the configured max upload size, default 1024 MB).
2. **Select pages/chapters** — for PDFs and EPUBs, Diana shows the total page or chapter count and lets you specify which to convert. Enter ranges and individual numbers separated by commas (e.g. `1-3, 5, 10-15`). Leave empty to convert the entire document.
3. **Configure TTS** — pick an engine, voice, and speed. These default to whatever is set in Settings but can be overridden per job.
4. **Preview voice** — click **Preview Voice** to hear a short sample with your selected engine, voice, and speed before committing.
5. **Convert** — click **Convert to Audio** to queue the job.

### Library

The **Library** page lists all conversion jobs.

- **Pending / In-progress** jobs show their current stage and a progress bar during synthesis.
- **Completed** jobs have an inline audio player, **Download**, **Rename**, **Move**, and **Delete** buttons.
- **Failed** jobs display an expandable error details section.
- **Search** jobs by filename, **filter** by status, and **sort** by date, name, or status.
- **Folders** — organise jobs into folders via the "Manage Folders" panel and per-job "Move" button.
- **Pagination** — browse large libraries 20 jobs at a time.

The page auto-refreshes while jobs are processing.

### News

The **News** page is a newspaper aggregator powered by RSS and AI summarisation.

1. **Add sources** — enter a name and homepage URL. Use **Edit** to attach one or more RSS feed URLs and assign the source to one or more groups.
2. **Organise sources** — sort by name or group; filter by group. Assign multiple groups per source (e.g. Finance, US News).
3. **Get Latest Stories** — requires an LLM configured in Settings. Diana scrapes each source (RSS first, then homepage, then archive.ph as a last resort), passes all articles to the LLM in a single batched call, and returns deduplicated top stories per category.
   - Stories older than 3 days are automatically discarded.
   - Categories: Finance, Politics, Technology & Science, Sports & Entertainment, World, Health, Other.
   - Max stories per category is configurable in Settings.
4. **Browse stories** — categories are collapsible. Each story shows source, importance score, summary, and Visit / Archive links (via archive.ph).
5. **Convert to Audio** — select all stories, a category, or individual stories, then convert to an MP3 job.
6. **Persistent** — the last fetched batch is stored in the database and reloaded automatically when you return to the page.
7. **Export sources** — download all your sources (names, URLs, RSS feeds, groups) as a `diana_sources.json` file to share with others or back up your configuration.
8. **Import sources** — upload a `diana_sources.json` file to bulk-add sources. If a source already exists (matched by homepage URL), choose to **append** the imported feeds/groups alongside existing ones or **overwrite** them entirely.

### Web URL to Audio

The **Web URL to Audio** page converts any webpage into an audiobook in one step.

1. Paste a URL.
2. Optionally enable LLM cleaning (requires LLM configured in Settings).
3. Pick engine, voice, and speed.
4. Click **Convert** — Diana scrapes the page, cleans the text, and queues a TTS job.

### Settings

The **Settings** page lets you configure defaults that apply to new jobs and the dashboard itself. All changes are saved to `config.yaml`.

| Section | Options |
|---------|---------|
| **TTS Engine** | Default engine, voice (dropdown), and speed |
| **Processing** | Max chunk size, output bitrate, silence gap between chunks |
| **Dashboard** | Theme (dark / light / device auto-detect), max upload size (MB) |
| **Model Paths** | Kokoro model + voices files, Piper model file |
| **LLM Text Cleaning** | Provider (OpenAI / Anthropic / Google), API key, model override, translation target language |
| **OpenAI TTS** | API key, model (tts-1 / tts-1-hd) |
| **ElevenLabs TTS** | API key, model ID |
| **News** | Max stories per category returned by the AI |

> **Note:** Theme and max upload size changes require an app restart to take effect.

### Terminate

Click the **Terminate** button in the sidebar to stop the server.

## TTS Engines

| Engine | Type | License | Quality |
|--------|------|---------|---------|
| **Kokoro** (default) | Local | Apache 2.0 | High — natural-sounding |
| **Piper** | Local | GPL-3.0 | Good — fast, lightweight |
| **OpenAI TTS** | Cloud | Proprietary | Very high — requires API key |
| **ElevenLabs** | Cloud | Proprietary | Very high — requires API key |

Cloud engines require API keys configured in Settings. They return MP3 audio directly and do not require ffmpeg for encoding.

## Optional LLM Features

Diana can use a large language model for two purposes:

1. **Text cleaning** — before TTS, send each text chunk to the LLM to strip tables, charts, citations, footnotes, and boilerplate. Significantly improves narration quality for academic papers and web articles. Also supports translating text to a target language.

2. **News summarisation** — used by the News page to summarise and deduplicate stories across all sources in a single batched API call.

Supported providers:

| Provider | Default model | API key env var |
|----------|--------------|----------------|
| OpenAI | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| Google | `gemini-2.0-flash` | `GOOGLE_API_KEY` |

For security, store API keys as environment variables and reference them in `config.yaml` as `${OPENAI_API_KEY}` rather than entering the raw key.

## Adding a New TTS Engine

1. Create a new file in `diana/tts/` (e.g., `my_engine.py`)
2. Implement the `TTSEngine` protocol from `diana/tts/base.py`:
   - `name` property
   - `initialize()` — load models
   - `synthesize(text, voice, speed)` — async, returns audio bytes
   - `list_voices()` — return available voices
   - `shutdown()` — release resources
   - `VOICES` class attribute — list of `TTSVoice` objects
3. Register it in `diana/tts/registry.py`

## Configuration

Diana uses a `config.yaml` file in the project root. Copy the example to get started:

```bash
cp config.example.yaml config.yaml
```

All settings can also be changed from the **Settings** page in the dashboard. Key configuration sections:

```yaml
tts:
  engine: kokoro          # kokoro | piper | openai_tts | elevenlabs
  voice: af_heart
  speed: 1.0
  openai_tts:
    api_key: "${OPENAI_API_KEY}"
    model: tts-1
  elevenlabs:
    api_key: "${ELEVENLABS_API_KEY}"
    model: eleven_monolingual_v1

llm:
  enabled: false
  provider: openai        # openai | anthropic | google
  api_key: "${OPENAI_API_KEY}"
  model: ""               # leave blank for provider default
  target_language: ""     # e.g. "English" to translate; blank = no translation
  chunk_size: 8000

news:
  max_stories_per_category: 5
```

The Streamlit-specific settings (theme, upload size, toolbar) are synced to `.streamlit/config.toml` automatically.

## Project Structure

```
diana/
├── run.py                  # Launch the dashboard (syncs config on start)
├── setup.sh                # One-command setup (macOS / Linux)
├── setup.bat               # One-command setup (Windows)
├── Diana.command            # Double-click launcher (macOS, created by setup)
├── Diana.bat                # Double-click launcher (Windows, created by setup)
├── config.yaml             # Your configuration
├── config.example.yaml     # Example config with defaults
├── .streamlit/
│   └── config.toml         # Auto-generated Streamlit settings
├── diana/
│   ├── config.py           # Config loading and saving
│   ├── models.py           # Job data model + page range parser
│   ├── database.py         # SQLite job tracking and news storage
│   ├── parsers/            # PDF, EPUB, TXT text extraction
│   ├── tts/                # Swappable TTS engine layer
│   │   ├── base.py         # TTSEngine protocol + TTSVoice
│   │   ├── kokoro_engine.py
│   │   ├── piper_engine.py
│   │   ├── openai_tts_engine.py
│   │   ├── elevenlabs_engine.py
│   │   └── registry.py     # Engine discovery
│   ├── llm/                # LLM client (OpenAI / Anthropic / Google)
│   │   ├── client.py
│   │   └── registry.py
│   ├── news/               # News scraping and summarisation
│   │   ├── scraper.py      # RSS-first scraper with archive.ph fallback
│   │   └── summarizer.py   # Batched LLM story extraction
│   ├── processing/         # Chunking, synthesis, merging pipeline
│   │   ├── chunker.py      # Smart text chunking
│   │   ├── cleaner.py      # Rule-based text cleaning
│   │   ├── llm_cleaner.py  # LLM-based text cleaning
│   │   ├── synthesizer.py  # Per-chunk TTS synthesis
│   │   ├── merger.py       # WAV → MP3 merging with ffmpeg
│   │   ├── pipeline.py     # Full extraction → audio pipeline
│   │   └── worker.py       # Background job worker
│   └── dashboard/          # Streamlit web UI
│       ├── Home.py         # Home page
│       ├── sidebar.py      # Shared sidebar, logo, global CSS
│       ├── static/         # Images (icon.jpeg, full.png)
│       └── pages/
│           ├── 1_Upload.py
│           ├── 2_Library.py
│           ├── 3_News.py
│           ├── 4_Web.py
│           └── 5_Settings.py
└── data/                   # Runtime data (uploads, output, models, SQLite DB)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Piper model not found` | Re-run `./setup.sh` (or `setup.bat`) to auto-download, or manually download from [piper releases](https://huggingface.co/rhasspy/piper-voices) and place it at the path shown in Settings |
| Upload size too small | Increase **Max upload size** in Settings, save, and restart |
| Theme not applying | Theme changes require a restart — stop the app and run `python run.py` again |
| `ffmpeg not found` | Install ffmpeg (see Prerequisites) and ensure it's on your PATH |
| News 403 errors | The site blocks scrapers — add an RSS feed URL via Edit (e.g. `https://www.ft.com/rss/home`) |
| News: no stories | Ensure an LLM is configured in Settings → LLM Text Cleaning |
| LLM module not found | Install the required provider: `pip install openai` / `pip install anthropic` / `pip install google-generativeai` |
| Git push fails for large files | Run `git config http.postBuffer 524288000` then push again |

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

## Changelog

### v1.0.0

Major feature release: cloud TTS, LLM cleaning, news aggregator, and web-to-audio.

- **Cloud TTS:** OpenAI TTS (tts-1 / tts-1-hd) and ElevenLabs engines added alongside Kokoro and Piper
- **LLM Text Cleaning:** Optional pre-processing via OpenAI, Anthropic, or Google Gemini — strips tables, charts, citations, boilerplate; supports translation
- **News Page:** Add newspaper sources with multiple RSS feeds and group tags; fetch top stories per category via a single batched LLM call; archive.ph fallback for paywalled sites; stories persisted across sessions; convert to audio
- **Web URL to Audio:** Paste any URL, scrape + clean + convert in one step
- **UI:** Sidebar nav items italic; all page titles italic; Settings moved to last sidebar position; news categories collapsible
- **News categories:** Merged to 7 (Technology & Science, Sports & Entertainment combined)
- **Config:** New `news.max_stories_per_category` setting; new `llm` section for API-based cleaning

### v0.3.0

Text cleaning, Piper fixes, and license update.

- **Text Cleaning:** Rule-based cleaning pipeline strips LaTeX, citations, URLs, and control characters before TTS — fixes "index out of bounds" crashes on academic documents
- **Piper Fix:** Voice parameter now correctly resolves to voice-specific model files with caching
- **Piper Fix:** Added `piper-tts` as a required dependency
- **UX:** Graceful termination — no more "Connection error" overlay after shutdown
- **UX:** Updated terminate confirmation message
- **Infrastructure:** Updated Piper references from rhasspy/piper to OHF-Voice/piper1-gpl
- **Infrastructure:** License changed from Apache 2.0 to GPL-3.0 (piper-tts compatibility)
- **Infrastructure:** Tests for text cleaner and Piper engine

### v0.2.0

Security, robustness, and UX improvements.

- **Security:** Sanitize uploaded filenames to prevent path traversal
- **Security:** Delete and terminate actions now require confirmation
- **Library:** Search by filename, filter by status, sort by date/name/status
- **Library:** Organise jobs into folders (create, move, remove)
- **Library:** Pagination (20 jobs per page)
- **Library:** Expandable error details for failed jobs
- **Upload:** Custom voice preview text
- **Upload:** Page range validation with inline feedback
- **Upload:** Double-submit prevention
- **Settings:** Model path validation with warnings on save
- **Infrastructure:** Apache 2.0 LICENSE, pyproject.toml, .gitignore improvements
- **Infrastructure:** Unit tests for models, config, database, and chunker
- **Infrastructure:** CI/CD via GitHub Actions (Python 3.10–3.13)

### v0.1.0

Initial release.

- Upload PDF, EPUB, and TXT files and convert to MP3
- Page/chapter range selection for PDFs and EPUBs
- Kokoro and Piper TTS engines with voice preview
- Library with audio playback, download, rename, and delete
- Configurable theme (dark / light / device auto-detect)
- Configurable max upload size
- Background job processing with progress tracking
- Modular engine architecture — add new TTS backends by implementing `TTSEngine`
