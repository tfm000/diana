"""Shared sidebar setup for all Diana pages — logo and terminate button."""

import os
import signal
import time
from pathlib import Path

import streamlit as st
from PIL import Image

STATIC_DIR = Path(__file__).parent / "static"


def get_icon_image() -> Image.Image:
    """Load the icon image for favicon and logo."""
    return Image.open(STATIC_DIR / "icon.jpeg")


_GLOBAL_FONT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500;1,600;1,700&display=swap');

[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] h1,
[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3,
[data-testid="stAppViewContainer"] h4,
[data-testid="stAppViewContainer"] h5,
[data-testid="stAppViewContainer"] h6,
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] input,
[data-testid="stAppViewContainer"] select,
[data-testid="stAppViewContainer"] textarea,
[data-testid="stAppViewContainer"] button {
    font-family: 'Cormorant Garamond', Georgia, 'Times New Roman', serif !important;
}

/* Sidebar nav text size */
[data-testid="stSidebarNav"] span {
    font-size: 1.1rem !important;
}

/* Sidebar logo size */
[data-testid="stLogo"] img {
    max-height: 12rem !important;
}

/* Audio player: full width and hide broken kebab download menu */
audio {
    width: 100% !important;
    min-height: 54px !important;
}
audio::-webkit-media-controls-enclosure {
    overflow: hidden;
}
audio::-webkit-media-controls-overflow-button {
    display: none !important;
}

/* Red terminate button in sidebar */
[data-testid="stSidebar"] button[kind="secondary"] {
    background-color: #d32f2f !important;
    color: white !important;
    border-color: #d32f2f !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background-color: #b71c1c !important;
    border-color: #b71c1c !important;
}
</style>
"""


def setup_sidebar() -> None:
    """Add the Diana logo, header font, and terminate button to the sidebar."""
    # If already terminated, show goodbye and stop
    if st.session_state.get("terminated", False):
        st.markdown(
            """
            <style>
            [data-testid="stStatusWidget"], .stException,
            div[data-testid="stConnectionStatus"] { display: none !important; }
            </style>
            <div style="text-align:center; padding:2rem;">
                <h2>Session ended</h2>
                <p>You may close this browser tab.</p>
            </div>
            <script>setTimeout(function(){ window.close(); }, 500);</script>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    # Inject literary font for all text on every page
    st.markdown(_GLOBAL_FONT_CSS, unsafe_allow_html=True)

    icon_path = STATIC_DIR / "icon.jpeg"
    if icon_path.exists():
        st.logo(str(icon_path), size="large")

    st.sidebar.divider()
    if st.session_state.get("confirm_terminate", False):
        st.sidebar.warning("This will end your time with Diana.")
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.button("Confirm", key="terminate_yes"):
                st.session_state["terminated"] = True
                st.markdown(
                    """
                    <style>
                    [data-testid="stStatusWidget"], .stException,
                    div[data-testid="stConnectionStatus"] { display: none !important; }
                    </style>
                    <div style="text-align:center; padding:2rem;">
                        <h2>Session ended</h2>
                        <p>You may close this browser tab.</p>
                    </div>
                    <script>setTimeout(function(){ window.close(); }, 500);</script>
                    """,
                    unsafe_allow_html=True,
                )
                time.sleep(1.5)
                os.kill(os.getpid(), signal.SIGTERM)
        with c2:
            if st.button("Cancel", key="terminate_no"):
                del st.session_state["confirm_terminate"]
                st.rerun()
    else:
        if st.sidebar.button("Terminate", type="secondary", use_container_width=True):
            st.session_state["confirm_terminate"] = True
            st.rerun()
