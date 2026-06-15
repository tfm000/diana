"""Pure-helper unit tests for the Voices-tab Piper download state machine (04-03).

The Settings *page* executes module-level ``st.*`` (``st.set_page_config``,
``st.tabs`` …) on import, which needs a Streamlit ScriptRunContext that does not
exist under pytest. But the download-state decision is deliberately factored into
Streamlit-FREE helpers — ``_download_action`` / ``_can_spawn_download`` /
``_new_dl_state`` — defined above any module-level ``st.*`` (mirroring the Phase-3
``resolve_selected_voice_id`` precedent). We therefore load ONLY those function
definitions out of the page source (AST-sliced) into a namespace with ``st`` and the
page's imports stubbed, so the real source is exercised without a Streamlit runtime.

Regression target (04-03 human-verify checkpoint): after Cancel, the worker now sets
a TERMINAL ``cancelled`` marker, and the action column derives "Resume" from it — the
row no longer stays stuck on "Cancel" (``done=False, error=None``). The spawn guard
must block a respawn only while genuinely in-flight or mid-cancel, and allow Resume
once the prior thread is terminal (no second writer on the same ``.part`` — Pitfall 3).
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PAGE_SRC = (
    Path(__file__).resolve().parent.parent
    / "diana" / "dashboard" / "pages" / "5_Settings.py"
).read_text(encoding="utf-8")

# AST-slice ONLY the pure, Streamlit-free helpers (no module-level st.* executes).
_WANTED = {"_new_dl_state", "_download_action", "_can_spawn_download"}


def _load_pure_helpers():
    """Exec just the wanted FunctionDefs from the page source into a clean namespace.

    ``st`` is stubbed (the helpers never call it; the stub only satisfies any stray
    reference and guarantees the test can never touch a real ScriptRunContext).
    """
    tree = ast.parse(_PAGE_SRC)
    wanted_nodes = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in _WANTED
    ]
    assert {n.name for n in wanted_nodes} == _WANTED, (
        "page must define the pure download helpers above any module-level st.*"
    )
    module = ast.Module(body=wanted_nodes, type_ignores=[])
    ns: dict = {"st": MagicMock()}
    exec(compile(module, str(_PAGE_SRC), "exec"), ns)  # noqa: S102 — trusted in-repo source
    return ns


_NS = _load_pure_helpers()
_new_dl_state = _NS["_new_dl_state"]
_download_action = _NS["_download_action"]
_can_spawn_download = _NS["_can_spawn_download"]


# --- _new_dl_state shape ----------------------------------------------------
def test_new_dl_state_has_terminal_cancelled_field():
    """A fresh record carries both the cancel REQUEST flag and the cancelled marker."""
    s = _new_dl_state(1234)
    assert s == {
        "downloaded": 0, "total": 1234, "done": False,
        "error": None, "cancel": False, "cancelled": False,
    }
    # Resume creates a fresh record -> genuinely in-flight again (D-06).
    assert _download_action(s) == "downloading"


# --- _download_action: full state -> label table ----------------------------
@pytest.mark.parametrize(
    "state, expected",
    [
        # fresh / cleared
        (None, "install"),
        ({}, "install"),
        (_new_dl_state(10), "downloading"),
        # genuinely in-flight (some bytes streamed)
        ({"done": False, "error": None, "cancel": False, "cancelled": False,
          "downloaded": 5, "total": 10}, "downloading"),
        # cancel requested, worker not yet stopped -> disabled "Cancelling…"
        ({"done": False, "error": None, "cancel": True, "cancelled": False,
          "downloaded": 5, "total": 10}, "cancelling"),
        # TERMINAL cancelled (worker set the marker) -> Resume  *** the bug fix ***
        ({"done": False, "error": None, "cancel": True, "cancelled": True,
          "downloaded": 5, "total": 10}, "resume"),
        # errored -> Resume
        ({"done": False, "error": "boom", "cancel": False, "cancelled": False,
          "downloaded": 5, "total": 10}, "resume"),
        # finished -> Installed/done
        ({"done": True, "error": None, "cancel": False, "cancelled": False,
          "downloaded": 10, "total": 10}, "done"),
        # done WINS over a lingering cancel request observed too late
        ({"done": True, "error": None, "cancel": True, "cancelled": False,
          "downloaded": 10, "total": 10}, "done"),
        # error WINS over a lingering cancel request
        ({"done": False, "error": "boom", "cancel": True, "cancelled": False,
          "downloaded": 5, "total": 10}, "resume"),
    ],
)
def test_download_action_table(state, expected):
    assert _download_action(state) == expected


def test_download_action_cancel_then_cancelled_transition():
    """The exact checkpoint bug: Cancel must lead to a Resume-able row, not stay stuck.

    Before the fix the post-cancel record was ``done=False, error=None`` so the action
    column kept showing Cancel forever. With the terminal ``cancelled`` marker the row
    goes downloading -> cancelling -> resume.
    """
    state = _new_dl_state(10)
    assert _download_action(state) == "downloading"  # in-flight, shows Cancel
    state["cancel"] = True                             # user clicks Cancel
    assert _download_action(state) == "cancelling"     # worker still exiting
    state["cancelled"] = True                           # worker set terminal marker
    assert _download_action(state) == "resume"          # Resume now offered (the fix)


# --- _can_spawn_download: respawn guard (Pitfall 3 / T-04-RETRIG) ------------
@pytest.mark.parametrize(
    "state, can_spawn",
    [
        (None, True),                                                  # nothing yet
        ({}, True),                                                    # cleared -> install
        (_new_dl_state(10), False),                                    # in-flight: block
        ({"done": False, "error": None, "cancel": True,
          "cancelled": False}, False),                                 # cancelling: block
        ({"done": False, "error": None, "cancel": True,
          "cancelled": True}, True),                                   # cancelled: Resume ok
        ({"done": False, "error": "boom", "cancel": False,
          "cancelled": False}, True),                                  # errored: Resume ok
        ({"done": True, "error": None, "cancel": False,
          "cancelled": False}, True),                                  # done: re-install ok
    ],
)
def test_can_spawn_download_guard(state, can_spawn):
    assert _can_spawn_download(state) is can_spawn


def test_spawn_guard_blocks_only_genuine_in_flight_and_cancelling():
    """Block exactly the two non-terminal phases; allow every terminal/absent phase."""
    blocked = [
        _new_dl_state(10),                                              # downloading
        {"done": False, "error": None, "cancel": True, "cancelled": False},  # cancelling
    ]
    allowed = [
        None,
        {},
        {"done": False, "error": None, "cancel": True, "cancelled": True},   # cancelled
        {"done": False, "error": "boom", "cancel": False, "cancelled": False},  # error
        {"done": True, "error": None, "cancel": False, "cancelled": False},  # done
    ]
    assert all(_can_spawn_download(s) is False for s in blocked)
    assert all(_can_spawn_download(s) is True for s in allowed)
