import logging
from pathlib import Path

import streamlit as st

from diana.config import get_config, save_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.tts.registry import get_engine_voices, list_engines
from diana.utils import detect_device_theme

logger = logging.getLogger(__name__)


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

_engines = list_engines()
_saved_engine = config.tts.engine
if _saved_engine not in _engines:
    logger.warning("Saved TTS engine %r no longer available; falling back to kokoro", _saved_engine)
    _saved_engine = "kokoro"
engine = st.selectbox(
    "Default Engine",
    _engines,
    index=_engines.index(_saved_engine),
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
_llm_provider_options = ["openai", "anthropic", "anthropic-cli", "google"]
_current_provider = config.llm.provider if config.llm.provider in _llm_provider_options else "openai"
llm_provider = st.selectbox(
    "Provider",
    _llm_provider_options,
    index=_llm_provider_options.index(_current_provider),
    disabled=not llm_enabled,
)
if llm_provider == "anthropic-cli":
    st.info(
        "Anthropic CLI uses your Claude Code login. Run `claude login` in a "
        "terminal first — no API key needed. Uses your Pro/Max subscription."
    )
    llm_api_key = ""
else:
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
if llm_enabled and llm_provider != "anthropic-cli" and llm_api_key and not _ENV_RE.match(llm_api_key.strip()):
    st.warning(
        "The API key will be stored in plaintext in config.yaml. "
        "Use `${YOUR_ENV_VAR}` to store a reference instead."
    )

# Live status mirroring diana.llm.registry.get_llm_config — keeps Settings
# honest about whether Upload/News will actually see a usable provider.
_key_typed = (llm_api_key or "").strip()
_key_unresolved = _key_typed.startswith("${")
if not llm_enabled:
    st.caption("LLM cleaning is disabled — text cleaning runs on-device (rule-based).")
elif llm_provider == "anthropic-cli":
    st.success(
        "Active: anthropic-cli (uses your local Claude Code login; no API key required)."
    )
elif not _key_typed:
    st.warning(
        "Not active: no API key set — cleaning falls back to rule-based (on-device). "
        "Nothing leaves your machine."
    )
elif _key_unresolved:
    st.warning(
        f"Not active: API key reference `{llm_api_key}` is unresolved (env var not set) "
        "— cleaning falls back to rule-based (on-device). Nothing leaves your machine."
    )
else:
    st.success(f"Active: {llm_provider} with API key configured.")

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
