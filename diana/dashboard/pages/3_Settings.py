import streamlit as st

from diana.config import get_config, save_config
from diana.tts.registry import list_engines

config = get_config()

st.header("Settings")

st.subheader("TTS Engine")

engine = st.selectbox(
    "Default Engine",
    list_engines(),
    index=list_engines().index(config.tts.engine),
)

voice = st.text_input("Default Voice ID", value=config.tts.voice)
speed = st.slider("Default Speed", min_value=0.5, max_value=2.0, value=config.tts.speed, step=0.1)

st.subheader("Processing")

chunk_max = st.number_input(
    "Max characters per chunk",
    min_value=500, max_value=10000,
    value=config.processing.chunk_max_chars, step=500,
)
bitrate = st.selectbox(
    "Output bitrate",
    ["128k", "192k", "256k", "320k"],
    index=["128k", "192k", "256k", "320k"].index(config.processing.output_bitrate),
)
gap_ms = st.number_input(
    "Silence between chunks (ms)",
    min_value=0, max_value=3000,
    value=config.processing.gap_ms, step=100,
)

st.subheader("Kokoro Model Paths")
kokoro_model = st.text_input("Model file", value=config.tts.kokoro.model_path)
kokoro_voices = st.text_input("Voices file", value=config.tts.kokoro.voices_path)

st.subheader("Piper Model Path")
piper_model = st.text_input("Model file ", value=config.tts.piper.model_path)

if st.button("Save Settings", type="primary"):
    config.tts.engine = engine
    config.tts.voice = voice
    config.tts.speed = speed
    config.processing.chunk_max_chars = chunk_max
    config.processing.output_bitrate = bitrate
    config.processing.gap_ms = gap_ms
    config.tts.kokoro.model_path = kokoro_model
    config.tts.kokoro.voices_path = kokoro_voices
    config.tts.piper.model_path = piper_model
    save_config(config)
    st.success("Settings saved.")
