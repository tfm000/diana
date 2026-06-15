"""One shared, cached voice enumerator for the dashboard (Upload + Settings).

Both the Upload picker and the Settings Default-Voice picker need an engine's voice
list on every Streamlit rerun, and enumeration can be costly (native_os shells
``say -v '?'``; piper globs the model dir + reads the bundled catalog). A
``@st.cache_data`` wrapper keeps tab switching and keystrokes from re-enumerating
(D-04 / threat T-03-12).

This module exists so the cache is ONE object shared across both pages rather than a
private ``_cached_voices`` per page. Installing (or, later, uninstalling) a Piper
voice writes ``{id}.onnx`` to ``model_dir()`` but cannot otherwise invalidate a
per-page cache, so an installed voice would not appear in the picker until an app
restart (the 04-03 install->use defect). ``clear_voice_cache`` lets the install-done
transition drop the cached enumeration so the new voice shows up in BOTH pickers
WITHOUT a restart.

The clear MUST be invoked from the Streamlit SCRIPT thread (the fragment poller / main
body on the install-done transition), NEVER from the download worker thread, which is
kept ``st.*``-free (T-04-SRC / ENGINE-01).
"""

import streamlit as st

from diana.config import get_config
from diana.tts.registry import get_engine_voices


@st.cache_data(show_spinner=False)
def cached_voices(engine_name: str):
    """Enumerate an engine's voices once per engine, cached across reruns (D-04).

    Shared by the Upload and Settings pages so both read the same cached list (and so
    one ``clear_voice_cache()`` refreshes both). config is read fresh inside (not a
    cache arg) — only the engine name keys the cache. TTSVoice is a plain dataclass,
    so the list is picklable and cache-safe.
    """
    return get_engine_voices(engine_name, config=get_config())


def clear_voice_cache() -> None:
    """Drop the cached voice enumeration so a just-installed voice appears at once.

    Called on the Piper install-DONE transition (and, when Plan 04-06 lands an
    uninstall path, on uninstall completion) from the SCRIPT thread. Clears this one
    shared ``cached_voices`` entry so the next rerun re-enumerates from disk and the
    new voice shows up in both the Upload and Settings Default-Voice pickers without
    an app restart. Cheap and idempotent — safe to call once per completed install.
    """
    cached_voices.clear()
