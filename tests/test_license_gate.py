"""Wave-0 RED/skip scaffold for the accept-once NC-license gate (Plan 03, HEAVY-02/03).

D-08: F5 + Fish are non-commercial. Before the FIRST install the user must accept
the license once; acceptance persists in ``app_settings`` so a re-install never
re-prompts, and it survives restart (a fresh DB connection). These tests round-trip
``accept_license`` -> ``license_accepted`` over a real temp SQLite DB and assert:

  - an un-accepted engine reads False;
  - after ``accept_license`` it reads True;
  - the flag survives a re-read (accept-once persistence, D-08);
  - accepting one engine does NOT accept another.

Symbols land in Wave 3; module home is the implementer's choice
(``diana.tts.heavy_install`` OR ``diana.tts.install_state``), so both are probed.
"""

import pytest

from diana.database import init_db

# --- Guarded probes: the license gate lands in Wave 3 -----------------------
_accept_license = None
_license_accepted = None
for _modname in ("diana.tts.heavy_install", "diana.tts.install_state"):
    try:  # pragma: no cover - import probe
        _mod = __import__(_modname, fromlist=["accept_license"])
    except ImportError:
        continue
    if _accept_license is None and hasattr(_mod, "accept_license"):
        _accept_license = _mod.accept_license
    if _license_accepted is None and hasattr(_mod, "license_accepted"):
        _license_accepted = _mod.license_accepted
_LICENSE_GATE_AVAILABLE = (
    _accept_license is not None and _license_accepted is not None
)


# --- D-08: accept-once persistence, scoped per engine -----------------------
@pytest.mark.skipif(
    not _LICENSE_GATE_AVAILABLE,
    reason="accept_license / license_accepted land in Wave 3",
)
def test_license_accept_once_persists(tmp_path):
    """Accepting F5's license persists (survives a re-read) and is engine-scoped."""
    db = str(tmp_path / "diana.db")
    init_db(db)

    # Un-accepted out of the box.
    assert _license_accepted(db, "f5") is False
    assert _license_accepted(db, "fish") is False

    # Accept F5 once.
    _accept_license(db, "f5")
    assert _license_accepted(db, "f5") is True

    # Survives a re-read (get_setting opens a fresh connection — D-08 persistence).
    assert _license_accepted(db, "f5") is True

    # Accepting F5 must NOT silently accept Fish (per-engine flag).
    assert _license_accepted(db, "fish") is False

    # A second accept is idempotent (re-install never re-prompts).
    _accept_license(db, "f5")
    assert _license_accepted(db, "f5") is True
