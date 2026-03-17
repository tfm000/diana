from pathlib import Path

import streamlit as st

from diana.config import get_config, save_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.tts.registry import get_engine_voices, list_engines
from diana.utils import detect_device_theme


def _sync_streamlit_config(max_upload_mb: int, theme: str = "device") -> None:
    """Update .streamlit/config.toml with current settings."""
    config_dir = Path(".streamlit")
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.toml"

    base = detect_device_theme() if theme == "device" else theme

    config_path.write_text(
        "[client]\n"
        'toolbarMode = "minimal"\n'
        "\n"
        "[browser]\n"
        "gatherUsageStats = false\n"
        "\n"
        "[server]\n"
        "headless = true\n"
        f"maxUploadSize = {max_upload_mb}\n"
        "\n"
        "[theme]\n"
        'font = "serif"\n'
        f'base = "{base}"\n'
    )

st.set_page_config(
    page_title="Diana's Settings",
    page_icon=get_icon_image(),
    layout="wide",
)

config = get_config()
setup_sidebar()

st.markdown("## *Settings*")

st.subheader("TTS Engine")

engine = st.selectbox(
    "Default Engine",
    list_engines(),
    index=list_engines().index(config.tts.engine),
)

# Voice dropdown populated from the selected engine
voices = get_engine_voices(engine, config=config)
voice_options = {v.name: v.id for v in voices}
voice_display = list(voice_options.keys())
default_voice_idx = 0
for i, v in enumerate(voices):
    if v.id == config.tts.voice:
        default_voice_idx = i
        break
selected_voice_name = st.selectbox(
    "Default Voice", voice_display, index=default_voice_idx, key=f"settings_voice_{engine}"
)
selected_voice_id = voice_options.get(selected_voice_name, "")

speed = st.slider(
    "Default Speed",
    min_value=0.5, max_value=2.0, value=config.tts.speed, step=0.1,
)

st.subheader("Processing")

chunk_max = st.number_input(
    "Max characters per chunk",
    min_value=500, max_value=10000,
    value=config.processing.chunk_max_chars, step=500,
)
bitrate = st.selectbox(
    "Output bitrate",
    ["128k", "192k", "256k", "320k"],
    index=["128k", "192k", "256k", "320k"].index(
        config.processing.output_bitrate
    ),
)
gap_ms = st.number_input(
    "Silence between chunks (ms)",
    min_value=0, max_value=3000,
    value=config.processing.gap_ms, step=100,
)

st.subheader("Dashboard")

theme_options = ["device", "light", "dark"]
theme = st.selectbox(
    "Theme",
    theme_options,
    index=theme_options.index(config.dashboard.theme),
)

max_upload_mb = st.number_input(
    "Max upload size (MB)",
    min_value=1, max_value=10240,
    value=config.dashboard.max_upload_mb, step=100,
)

st.subheader("Kokoro Model Paths")
kokoro_model = st.text_input(
    "Model file", value=config.tts.kokoro.model_path
)
kokoro_voices = st.text_input(
    "Voices file", value=config.tts.kokoro.voices_path
)

st.subheader("Piper Model Path")
piper_model = st.text_input(
    "Piper model file", value=config.tts.piper.model_path
)

# ---------------------------------------------------------------------------
# LLM Text Cleaning (optional)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("LLM Text Cleaning (Optional)")
st.info(
    "For security, enter your API key as an environment variable reference like "
    "`${OPENAI_API_KEY}` and set the actual key in your shell. "
    "The placeholder is saved to config.yaml, not the real key."
)

llm_enabled = st.toggle("Enable LLM cleaning", value=config.llm.enabled)
llm_provider = st.selectbox(
    "Provider",
    ["openai", "anthropic", "google"],
    index=["openai", "anthropic", "google"].index(config.llm.provider),
    disabled=not llm_enabled,
)
llm_api_key = st.text_input(
    "API Key",
    value=config.llm.api_key,
    type="password",
    placeholder="${OPENAI_API_KEY}",
    disabled=not llm_enabled,
)
llm_model = st.text_input(
    "Model override (leave blank for default)",
    value=config.llm.model,
    placeholder="gpt-4o-mini",
    disabled=not llm_enabled,
)
llm_language = st.text_input(
    "Translate to language (leave blank to skip)",
    value=config.llm.target_language,
    placeholder="e.g. English, Spanish",
    disabled=not llm_enabled,
)
llm_max_concurrent = st.number_input(
    "Max concurrent LLM calls",
    min_value=1, max_value=16,
    value=config.llm.max_concurrent_calls, step=1,
    help="Number of text chunks processed in parallel. Higher values are faster but may hit API rate limits.",
    disabled=not llm_enabled,
)

_ENV_RE = __import__("re").compile(r"^\$\{[A-Z_][A-Z0-9_]*\}$")
if llm_enabled and llm_api_key and not _ENV_RE.match(llm_api_key.strip()):
    st.warning(
        "The API key will be stored in plaintext in config.yaml. "
        "Use `${YOUR_ENV_VAR}` to store a reference instead."
    )

# ---------------------------------------------------------------------------
# OpenAI TTS (optional)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("OpenAI TTS (Optional)")
st.info(
    "Use OpenAI's cloud TTS for higher quality audio. "
    "Select **openai_tts** as the engine in Upload to use this."
)
openai_tts_key = st.text_input(
    "OpenAI API Key",
    value=config.tts.openai_tts.api_key,
    type="password",
    placeholder="${OPENAI_API_KEY}",
    key="openai_tts_key_input",
)
openai_tts_model = st.selectbox(
    "Model",
    ["tts-1", "tts-1-hd"],
    index=0 if config.tts.openai_tts.model == "tts-1" else 1,
)
if openai_tts_key and not _ENV_RE.match(openai_tts_key.strip()):
    st.warning("API key will be stored in plaintext. Use `${OPENAI_API_KEY}` instead.")

# ---------------------------------------------------------------------------
# ElevenLabs TTS (optional)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("ElevenLabs TTS (Optional)")
st.info(
    "Use ElevenLabs for premium voice quality. "
    "Select **elevenlabs** as the engine in Upload to use this."
)
elevenlabs_key = st.text_input(
    "ElevenLabs API Key",
    value=config.tts.elevenlabs.api_key,
    type="password",
    placeholder="${ELEVENLABS_API_KEY}",
    key="elevenlabs_key_input",
)
elevenlabs_model = st.text_input(
    "Model ID",
    value=config.tts.elevenlabs.model,
    placeholder="eleven_monolingual_v1",
)
if elevenlabs_key and not _ENV_RE.match(elevenlabs_key.strip()):
    st.warning("API key will be stored in plaintext. Use `${ELEVENLABS_API_KEY}` instead.")

# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------
st.divider()
st.subheader("News")
news_max_stories = st.number_input(
    "Max stories per category",
    min_value=1,
    max_value=20,
    value=config.news.max_stories_per_category,
    step=1,
    help="Maximum stories the AI will return per category each time you fetch.",
)

st.divider()

if st.button("Save Settings", type="primary"):
    # Validate model paths for the selected engine
    warnings = []
    if engine == "kokoro":
        if not Path(kokoro_model).exists():
            warnings.append(f"Kokoro model file not found: {kokoro_model}")
        if not Path(kokoro_voices).exists():
            warnings.append(f"Kokoro voices file not found: {kokoro_voices}")
    elif engine == "piper":
        if not Path(piper_model).exists():
            warnings.append(f"Piper model file not found: {piper_model}")

    config.tts.engine = engine
    config.tts.voice = selected_voice_id
    config.tts.speed = speed
    config.processing.chunk_max_chars = chunk_max
    config.processing.output_bitrate = bitrate
    config.processing.gap_ms = gap_ms
    config.dashboard.max_upload_mb = max_upload_mb
    config.dashboard.theme = theme
    config.tts.kokoro.model_path = kokoro_model
    config.tts.kokoro.voices_path = kokoro_voices
    config.tts.piper.model_path = piper_model
    config.tts.openai_tts.api_key = openai_tts_key
    config.tts.openai_tts.model = openai_tts_model
    config.tts.elevenlabs.api_key = elevenlabs_key
    config.tts.elevenlabs.model = elevenlabs_model or "eleven_monolingual_v1"
    config.llm.enabled = llm_enabled
    config.llm.provider = llm_provider
    config.llm.api_key = llm_api_key
    config.llm.model = llm_model
    config.llm.target_language = llm_language
    config.llm.max_concurrent_calls = int(llm_max_concurrent)
    config.news.max_stories_per_category = int(news_max_stories)
    save_config(config)
    _sync_streamlit_config(max_upload_mb, theme)

    for w in warnings:
        st.warning(w)
    if warnings:
        st.success("Settings saved, but model files above are missing. TTS may fail until they are provided.")
    else:
        st.success("Settings saved. Restart the app for theme and upload size changes to take effect.")
