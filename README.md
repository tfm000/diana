# Diana — Text-to-Speech Document Converter <!-- v0.3.0 -->

<table>
<tr>
<td width="40%">
   <img src="diana/dashboard/static/full.png" alt="Diana" height="400">
</td>
<td valign="top" style="padding-left: 24px;">

Diana converts PDF, EPUB, and TXT documents into high-quality MP3 audiobooks using local AI text-to-speech models. All processing runs on your machine — no API keys or cloud services required.

**Features**
- Upload PDF, EPUB, or TXT files
- Select specific pages or chapters to convert
- Multiple TTS engines (Kokoro, Piper) — swappable
- Choose voice and speed per job
- Preview voices before converting
- Track jobs and play/download audio in the Library
- Configurable theme (dark, light, or auto-detect)
- All local — no internet required after setup

**Quick Start**
1. Install prerequisites (Python 3.10+, ffmpeg)
2. `pip install -r requirements.txt`
3. Download Kokoro model files (see below)
4. `python run.py`
5. Open [http://localhost:8501](http://localhost:8501)

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

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment:**

   macOS / Linux:
   ```bash
   source .venv/bin/activate
   ```

   Windows:
   ```bash
   .venv\Scripts\activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Download the Kokoro TTS model files** (~340 MB total):
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

6. **Copy the example config:**
   ```bash
   cp config.example.yaml config.yaml
   ```

## Usage

**Start Diana:**
```bash
python run.py
```

Open http://localhost:8501 in your browser.

### Home

The landing page displays Diana's artwork and quick links to Upload, Library, and Settings.

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
- **Folders** — organize jobs into folders via the "Manage Folders" panel and per-job "Move" button.
- **Pagination** — browse large libraries 20 jobs at a time.
- Click **Delete** to remove a job — a confirmation prompt prevents accidental deletion.

The page auto-refreshes while jobs are processing.

### Settings

The **Settings** page lets you configure defaults that apply to new jobs and the dashboard itself. All changes are saved to `config.yaml`.

| Section | Options |
|---------|---------|
| **TTS Engine** | Default engine, voice (dropdown), and speed |
| **Processing** | Max chunk size, output bitrate, silence gap between chunks |
| **Dashboard** | Theme (dark / light / device auto-detect), max upload size (MB) |
| **Model Paths** | Kokoro model + voices files, Piper model file |

> **Note:** Theme and max upload size changes require an app restart to take effect.

### Terminate

Click the **Terminate** button in the sidebar to stop the server.

## TTS Engines

| Engine | License | Runs Locally | Quality |
|--------|---------|-------------|---------|
| **Kokoro** (default) | Apache 2.0 | Yes | High — natural-sounding |
| **Piper** | GPL-3.0 | Yes | Good — fast, lightweight |

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

All settings can also be changed from the **Settings** page in the dashboard. The Streamlit-specific settings (theme, upload size, toolbar) are synced to `.streamlit/config.toml` automatically.

## Project Structure

```
diana/
├── run.py                  # Launch the dashboard (syncs config on start)
├── config.yaml             # Your configuration
├── config.example.yaml     # Example config with defaults
├── .streamlit/
│   └── config.toml         # Auto-generated Streamlit settings
├── diana/
│   ├── config.py           # Config loading and saving
│   ├── models.py           # Job data model + page range parser
│   ├── database.py         # SQLite job tracking
│   ├── parsers/            # PDF, EPUB, TXT text extraction
│   ├── tts/                # Swappable TTS engine layer
│   │   ├── base.py         # TTSEngine protocol + TTSVoice
│   │   ├── kokoro_engine.py
│   │   ├── piper_engine.py
│   │   └── registry.py     # Engine discovery
│   ├── processing/         # Chunking, synthesis, merging pipeline
│   │   ├── chunker.py      # Smart text chunking
│   │   ├── synthesizer.py  # Per-chunk TTS synthesis
│   │   ├── merger.py       # WAV → MP3 merging with ffmpeg
│   │   ├── pipeline.py     # Full extraction → audio pipeline
│   │   └── worker.py       # Background job worker
│   └── dashboard/          # Streamlit web UI
│       ├── Home.py         # Home page
│       ├── sidebar.py      # Shared sidebar, logo, global CSS
│       ├── static/         # Images (icon.jpeg, full.png)
│       └── pages/          # Upload, Library, Settings
└── data/                   # Runtime data (uploads, output, models, SQLite DB)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Piper model not found` | Download a Piper ONNX model from [piper releases](https://huggingface.co/rhasspy/piper-voices) and place it at the path shown in Settings |
| Upload size too small | Increase **Max upload size** in Settings, save, and restart |
| Theme not applying | Theme changes require a restart — stop the app and run `python run.py` again |
| `ffmpeg not found` | Install ffmpeg (see Prerequisites) and ensure it's on your PATH |
| Git push fails for large files | Run `git config http.postBuffer 524288000` then push again |

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

## Changelog

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
- **Library:** Organize jobs into folders (create, move, remove)
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
