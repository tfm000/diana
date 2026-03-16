"""Shared sidebar setup for all Diana pages — logo and terminate button."""

import os
import signal
from pathlib import Path

import streamlit as st
from PIL import Image

STATIC_DIR = Path(__file__).parent / "static"


def get_icon_image() -> Image.Image:
    """Load the icon image for favicon and logo."""
    return Image.open(STATIC_DIR / "icon.jpeg")


def setup_sidebar() -> None:
    """Add the Diana logo and terminate button to the sidebar."""
    icon_path = STATIC_DIR / "icon.jpeg"
    if icon_path.exists():
        st.logo(str(icon_path))

    st.sidebar.divider()
    if st.sidebar.button("Terminate", type="secondary", use_container_width=True):
        os.kill(os.getpid(), signal.SIGTERM)
