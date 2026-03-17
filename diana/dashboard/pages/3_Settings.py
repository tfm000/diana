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

st.header("Settings")

st.subheader("TTS Engine")

engine = st.selectbox(
    "Default Engine",
    list_engines(),
    index=list_engines().index(config.tts.engine),
)

# Voice dropdown populated from the selected engine
voices = get_engine_voices(engine)
voice_options = {v.name: v.id for v in voices}
voice_display = list(voice_options.keys())
default_voice_idx = 0
for i, v in enumerate(voices):
    if v.id == config.tts.voice:
        default_voice_idx = i
        break
selected_voice_name = st.selectbox(
    "Default Voice", voice_display, index=default_voice_idx
)
selected_voice_id = voice_options[selected_voice_name]

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
    save_config(config)
    _sync_streamlit_config(max_upload_mb, theme)

    for w in warnings:
        st.warning(w)
    if warnings:
        st.success("Settings saved, but model files above are missing. TTS may fail until they are provided.")
    else:
        st.success("Settings saved. Restart the app for theme and upload size changes to take effect.")
