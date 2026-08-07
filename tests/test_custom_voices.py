"""Wave-0 RED/skip scaffold for the reusable Custom Voices layer (Plan 05, HEAVY-02).

D-11..D-15 / V12: F5 voice cloning needs user reference clips. ``custom_voices``
validates an uploaded/recorded clip + transcript (never crashing — the Phase-4
import-rejection pattern), lands the file under a per-user dir with the
``safe_voice_dest`` path-safety guard (basename + ext allow-list + containment), and
round-trips named-voice metadata through ``app_settings``. These tests assert:

  - ``validate_clip(audio_path, transcript)`` returns a ``(ok, msg)`` tuple and NEVER
    raises — accepting a ~2-12 s clip with a non-empty transcript (incl. 16 kHz,
    Pitfall 5/7), rejecting a too-short clip, an empty/whitespace transcript, and a
    disallowed format;
  - ``safe_custom_voice_dest(name)`` strips path components, enforces a
    ``.wav``/``.mp3``/``.txt`` allow-list, and raises ``ValueError`` on a traversal /
    disallowed extension (mirrors ``catalog.safe_voice_dest``);
  - ``save_custom_voice`` / ``list_custom_voices`` / ``remove_custom_voice`` round-trip
    over a temp DB, and a malformed stored value degrades to an empty list rather than
    raising (T-04-LBLJSON analog).

Symbols land in Wave 5 (module home ``diana.tts.custom_voices``); collection stays
GREEN until then.
"""

import contextlib
import json
import sqlite3

import pytest

from diana.database import init_db

# --- Guarded probes: the Custom Voices layer lands in Wave 5 ----------------
_validate_clip = _safe_dest = None
_save_voice = _list_voices = _remove_voice = None
with contextlib.suppress(ImportError):
    import diana.tts.custom_voices as _cv

    _validate_clip = getattr(_cv, "validate_clip", None)
    _safe_dest = getattr(_cv, "safe_custom_voice_dest", None)
    _save_voice = getattr(_cv, "save_custom_voice", None)
    _list_voices = getattr(_cv, "list_custom_voices", None)
    _remove_voice = getattr(_cv, "remove_custom_voice", None)
    _name_for = getattr(_cv, "_name_for", None)

_VALIDATE_AVAILABLE = _validate_clip is not None
_DEST_AVAILABLE = _safe_dest is not None
_CRUD_AVAILABLE = all(x is not None for x in (_save_voice, _list_voices, _remove_voice))
_LIST_AVAILABLE = _list_voices is not None
_NAME_FOR_AVAILABLE = _name_for is not None


def _ids_of(listed):
    """Best-effort voice-id extraction across list_custom_voices' possible shapes."""
    out = []
    for item in listed:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out.append(item.get("id") or item.get("voice_id") or item.get("name"))
        else:
            out.append(getattr(item, "id", None) or getattr(item, "name", None))
    return out


def _save_one(save_fn, db, engine, voice_id, wav, txt):
    """Call save_custom_voice across its documented signature shapes (db, engine first)."""
    meta = {"id": voice_id, "name": "My Voice",
            "ref_file": str(wav), "ref_text": txt.read_text(encoding="utf-8")}
    attempts = (
        lambda: save_fn(db, engine, voice_id, meta),                      # (db,engine,id,meta)
        lambda: save_fn(db, engine, meta),                                # (db,engine,meta)
        lambda: save_fn(db, engine, voice_id, str(wav), txt.read_text(encoding="utf-8")),  # (db,engine,id,ref,text)
        lambda: save_fn(db, engine, "My Voice", str(wav), txt.read_text(encoding="utf-8")),
    )
    last = None
    for attempt in attempts:
        try:
            return attempt()
        except TypeError as e:  # signature mismatch — try the next documented shape
            last = e
    raise last


# --- D-13 / Pitfall 5: accept a good 16 kHz clip ----------------------------
@pytest.mark.skipif(not _VALIDATE_AVAILABLE, reason="validate_clip lands in Wave 5")
def test_validate_clip_accepts_good_16khz_clip(temp_clip):
    """A ~3 s 16 kHz clip + non-empty transcript validates True (sub-24 kHz OK)."""
    wav, txt = temp_clip(seconds=3.0, samplerate=16000)
    ok, msg = _validate_clip(str(wav), txt.read_text(encoding="utf-8"))
    assert ok is True
    assert isinstance(msg, str)


# --- D-13: reject an empty/whitespace transcript ----------------------------
@pytest.mark.skipif(not _VALIDATE_AVAILABLE, reason="validate_clip lands in Wave 5")
def test_validate_clip_rejects_empty_transcript(temp_clip):
    """A blank transcript is rejected with a message (D-12 transcript is required)."""
    wav, _txt = temp_clip(seconds=3.0)
    ok, msg = _validate_clip(str(wav), "   ")
    assert ok is False
    assert msg


# --- D-13 / Pitfall 7: reject a too-short clip ------------------------------
@pytest.mark.skipif(not _VALIDATE_AVAILABLE, reason="validate_clip lands in Wave 5")
def test_validate_clip_rejects_too_short(temp_clip):
    """A sub-second clip is below the clone floor and rejected (never crashes)."""
    wav, txt = temp_clip(seconds=0.4)
    ok, msg = _validate_clip(str(wav), txt.read_text(encoding="utf-8"))
    assert ok is False
    assert msg


# --- D-13: a disallowed format is rejected and NEVER raises -----------------
@pytest.mark.skipif(not _VALIDATE_AVAILABLE, reason="validate_clip lands in Wave 5")
def test_validate_clip_disallowed_format_never_raises(tmp_path):
    """Junk/unsupported audio -> (False, msg), never an exception (import-reject pattern)."""
    junk = tmp_path / "clip.bin"
    junk.write_bytes(b"not audio at all")
    try:
        ok, msg = _validate_clip(str(junk), "a perfectly valid transcript")
    except Exception as e:  # noqa: BLE001 - the contract is "never raises"
        pytest.fail(f"validate_clip must never raise, got {e!r}")
    assert ok is False
    assert msg


# --- V12: safe_custom_voice_dest contains the leaf under the per-user dir ----
@pytest.mark.skipif(not _DEST_AVAILABLE, reason="safe_custom_voice_dest lands in Wave 5")
def test_safe_custom_voice_dest_contains_under_dir(tmp_data_paths):
    """A clean name resolves to a Path inside custom_voices_dir()."""
    dest = _safe_dest("my voice.wav")
    root = tmp_data_paths["custom_voices_dir"]
    assert dest.name == "my voice.wav"
    assert str(dest.resolve()).startswith(str(root.resolve()))


# --- V12: path components are stripped (basename) ---------------------------
@pytest.mark.skipif(not _DEST_AVAILABLE, reason="safe_custom_voice_dest lands in Wave 5")
def test_safe_custom_voice_dest_strips_path_components(tmp_data_paths):
    """An absolute/traversal path with an allowed ext is reduced to its leaf, contained."""
    dest = _safe_dest("/etc/cron.d/evil.wav")
    root = tmp_data_paths["custom_voices_dir"]
    assert dest.name == "evil.wav"
    assert str(dest.resolve()).startswith(str(root.resolve()))


# --- V12: a disallowed extension raises ValueError --------------------------
@pytest.mark.skipif(not _DEST_AVAILABLE, reason="safe_custom_voice_dest lands in Wave 5")
def test_safe_custom_voice_dest_rejects_bad_extension(tmp_data_paths):
    """Only .wav/.mp3/.txt are accepted; anything else raises ValueError."""
    for bad in ("evil.sh", "payload.exe", "script.py"):
        with pytest.raises(ValueError):
            _safe_dest(bad)


# --- V12 / T-05-PATH: a traversal attempt raises ValueError -----------------
@pytest.mark.skipif(not _DEST_AVAILABLE, reason="safe_custom_voice_dest lands in Wave 5")
def test_safe_custom_voice_dest_rejects_traversal(tmp_data_paths):
    """A ../ traversal (whose leaf has no allowed ext) is rejected with ValueError."""
    with pytest.raises(ValueError):
        _safe_dest("../../etc/passwd")


# --- D-14: named-voice metadata round-trips through app_settings ------------
@pytest.mark.skipif(not _CRUD_AVAILABLE, reason="custom-voice CRUD lands in Wave 5")
def test_custom_voice_metadata_roundtrip(tmp_path, tmp_data_paths, temp_clip):
    """save -> list shows it; remove -> list no longer shows it (D-14 persistent library)."""
    db = str(tmp_path / "diana.db")
    init_db(db)
    wav, txt = temp_clip(seconds=3.0)

    saved_id = _save_one(_save_voice, db, "f5", "myvoice", wav, txt)
    listed = _list_voices(db, "f5")
    assert len(listed) >= 1, "a saved custom voice must appear in list_custom_voices"

    target = saved_id if (saved_id and saved_id in _ids_of(listed)) else "myvoice"
    _remove_voice(db, "f5", target)
    assert target not in _ids_of(_list_voices(db, "f5"))


# --- CR-02: an mp3-named upload is saved with .mp3 extension, not .wav ------
@pytest.mark.skipif(not _CRUD_AVAILABLE, reason="custom-voice CRUD lands in Wave 5")
def test_save_mp3_named_upload_resolves_mp3_dest(tmp_path, tmp_data_paths, temp_clip):
    """An upload with .mp3 in its name lands as <id>.mp3, not <id>.wav (CR-02).

    Synthesis engines (F5, Fish) choose their decoder by file extension.  Saving an
    MP3 upload as .wav causes a silent extension mismatch that only fails at synthesis
    time.  The fix: _ext_for_src derives the extension from audio_src.name so the
    on-disk file carries the correct suffix.  custom_voice_ref must then resolve it.
    """
    import io

    db = str(tmp_path / "diana.db")
    init_db(db)

    # Write a real WAV clip but expose it as an upload object whose .name ends in .mp3
    # (simulating an st.file_uploader result for an MP3 file).
    wav, txt = temp_clip(seconds=3.0)
    raw_bytes = wav.read_bytes()

    class _FakeUpload(io.BytesIO):
        name = "reference.mp3"

    upload = _FakeUpload(raw_bytes)

    ok, msg = _save_voice(db, "f5", "Mp3 Voice", upload, txt.read_text(encoding="utf-8"))
    assert ok, f"save_custom_voice rejected the mp3-named upload: {msg}"

    # The saved clip must resolve from custom_voice_ref and appear in list_custom_voices.
    import diana.tts.custom_voices as _cv

    # custom_voice_ref should find the .mp3 file (not fail looking for .wav)
    from diana import paths as _paths

    cv_dir = _paths.custom_voices_dir()
    mp3_files = list(cv_dir.glob("*.mp3"))
    assert mp3_files, "save_custom_voice must write <id>.mp3, not <id>.wav, for an mp3 upload"

    vid = mp3_files[0].stem
    ref_path, ref_text = _cv.custom_voice_ref(vid)
    assert ref_path.endswith(".mp3"), f"custom_voice_ref must return the .mp3 path, got {ref_path}"

    # list_custom_voices must enumerate the mp3-backed voice
    listed_ids = _ids_of(_list_voices(db, "f5"))
    assert vid in listed_ids, "list_custom_voices must enumerate mp3-backed custom voices"


# --- T-04-LBLJSON: a malformed stored value degrades, never crashes ---------
@pytest.mark.skipif(not _LIST_AVAILABLE, reason="list_custom_voices lands in Wave 5")
def test_list_custom_voices_tolerates_malformed_json(tmp_path, tmp_data_paths):
    """A corrupt app_settings value -> an empty/clean list, never an exception."""
    db = str(tmp_path / "diana.db")
    init_db(db)
    from diana.database import set_setting

    set_setting(db, "voice.custom.f5.x", "{not valid json")
    # Corrupt every stored value so whatever key the lister reads is malformed.
    conn = sqlite3.connect(db)
    conn.execute("UPDATE app_settings SET value = ?", ("{still not json",))
    conn.commit()
    conn.close()

    try:
        listed = _list_voices(db, "f5")
    except Exception as e:  # noqa: BLE001 - the contract is "degrade, never raise"
        pytest.fail(f"list_custom_voices must tolerate malformed JSON, got {e!r}")
    assert isinstance(listed, (list, tuple))


# --- Fresh machine: enumeration reads the CONFIGURED DB, not platformdirs ----
@pytest.mark.skipif(not _LIST_AVAILABLE, reason="list_custom_voices lands in Wave 5")
def test_list_custom_voices_reads_configured_db_on_a_fresh_machine(
    tmp_path, tmp_data_paths, monkeypatch
):
    """A no-``db_path`` enumeration resolves through the config, not ``paths.db_path()``.

    This is the deterministic form of the CI failure (run 31129161528): on a fresh
    machine — a CI runner, or a first launch — the per-user data dir does not exist
    yet, so the raw platformdirs path is UNOPENABLE and ``sqlite3.connect`` raises
    ``unable to open database file``. It also pins the wrong-DB half of the same bug:
    every other caller (``voice_labels`` / ``install_state``) is handed
    ``config.storage.database_path`` explicitly, so enumeration must read the same DB
    those writes land in.

    The fresh machine is simulated in-process (no ``$HOME`` juggling, so it holds
    identically on every OS and on CI): ``paths.data_dir``/``db_path`` point at a
    directory that was never created, while the configured path points at a real
    initialized DB holding the voice's display name. Reading the name back proves the
    CONFIGURED DB was used; not raising proves the fresh dir was never touched.
    """
    import diana.config as C
    from diana import paths
    from diana.database import set_setting

    configured_dir = tmp_path / "configured"
    configured_dir.mkdir()
    db = str(configured_dir / "diana.db")
    init_db(db)
    set_setting(db, "voice.custom.my-voice", json.dumps({"name": "My Voice"}))

    cfg = C.load_config()
    cfg.storage.database_path = db
    monkeypatch.setattr(C, "get_config", lambda *a, **k: cfg)

    # The fresh-machine per-user dir: never created, so opening it would raise.
    missing = tmp_path / "no-such-per-user-dir"
    monkeypatch.setattr(paths, "data_dir", lambda: missing)
    monkeypatch.setattr(paths, "db_path", lambda: missing / "diana.db")

    # The filesystem IS the index — one clip makes one enumerable voice.
    (tmp_data_paths["custom_voices_dir"] / "my-voice.wav").write_bytes(b"clip")

    try:
        listed = _list_voices()  # no db_path -> _default_db_path()
    except Exception as e:  # noqa: BLE001 - a fresh machine must never crash enumeration
        pytest.fail(f"enumeration must survive an absent per-user data dir, got {e!r}")

    assert "my-voice" in _ids_of(listed), "the clip on disk must enumerate as a voice"
    names = [getattr(v, "name", None) for v in listed]
    assert "My Voice" in names, (
        "the display name must come from the CONFIGURED db, proving _default_db_path "
        f"resolved through get_config().storage.database_path; got {names}"
    )


# --- T-05-LBLJSON: an unopenable DB degrades to the id, never raises --------
@pytest.mark.skipif(not _NAME_FOR_AVAILABLE, reason="_name_for lands in Wave 5")
def test_name_for_degrades_when_the_db_cannot_be_opened(tmp_path):
    """A DB-level failure falls back to the id, like an absent/malformed value does.

    ``sqlite3.Error`` (not just ``OperationalError``) is the caught breadth: any
    database problem — a directory that does not exist, a locked or corrupt file —
    must degrade a display name, never take down a voice list.
    """
    unopenable = str(tmp_path / "no-such-dir" / "diana.db")
    try:
        name = _name_for(unopenable, "my-voice")
    except Exception as e:  # noqa: BLE001 - the contract is "degrade, never raise"
        pytest.fail(f"_name_for must tolerate an unopenable DB, got {e!r}")
    assert name == "my-voice", "an unreadable DB falls back to the id"
