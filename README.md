# Diana — Text-to-Speech Document Converter

Diana converts PDF, EPUB, and TXT documents into high-quality MP3 audiobooks using local AI text-to-speech models. All processing runs on your machine — no API keys or cloud services required.

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
   git clone <repo-url> diana
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

### Upload

Navigate to the **Upload** page. Select a PDF, EPUB, or TXT file, choose a TTS engine and voice, then click **Convert to Audio**. Use the **Preview Voice** button to hear a sample before converting.

### Library

The **Library** page shows all jobs with their status. Active jobs display a progress bar. Completed jobs have an audio player and download button.

### Settings

The **Settings** page lets you change the default TTS engine, voice, speed, and audio processing options. Changes are saved to `config.yaml`.

### Terminate

Click the **Terminate** button in the sidebar to stop the server.

## TTS Engines

| Engine | License | Runs Locally | Quality |
|--------|---------|-------------|---------|
| **Kokoro** (default) | Apache 2.0 | Yes | High — natural-sounding |
| **Piper** | MIT | Yes | Good — fast, lightweight |

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

## Project Structure

```
diana/
├── run.py                  # Launch the dashboard
├── config.yaml             # Your configuration
├── diana/
│   ├── config.py           # Config loading
│   ├── models.py           # Job data model
│   ├── database.py         # SQLite job tracking
│   ├── parsers/            # PDF, EPUB, TXT text extraction
│   ├── tts/                # Swappable TTS engine layer
│   ├── processing/         # Chunking, synthesis, merging pipeline
│   └── dashboard/          # Streamlit web UI
└── data/                   # Runtime data (uploads, output, models)
```
