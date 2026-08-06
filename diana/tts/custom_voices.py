"""Engine-agnostic Custom Voices library — user reference clips for voice cloning.

Cloning engines (F5 now; Fish in 05-07) have NO baked-in voices: they clone a voice
from a short reference clip plus that clip's EXACT transcript. This module is the ONE
shared pool any cloning engine reuses (D-11): a user supplies a reference voice TWO
ways — upload an audio file + a transcript, OR record in-app (``st.audio_input``) +
type the transcript — and it is validated, landed on disk under a per-user dir with
the ``catalog.safe_voice_dest`` path-safety guard, named, listed, reused across jobs,
and removed like any other voice (D-14). The transcript is ALWAYS user-provided — no
auto-transcribe, no speech-to-text dependency is added (D-12).

ENGINE-AGNOSTIC storage (D-11): storage is NOT keyed by engine — one shared pool.
  Files: ``custom_voices_dir()/<id>.wav`` + ``<id>.txt`` (the filesystem IS the index,
    the ``list_installed_piper_voice_ids`` lane).
  Display metadata: the ``app_settings`` key ``voice.custom.<id>`` = JSON ``{"name": ...}``
    (NO engine segment — the ``voice_labels`` pattern, ``voice_labels.py:41-82``).

Four in-repo analogs, mirrored verbatim:
  1. **Path safety (T-05-PATH).** ``safe_custom_voice_dest`` copies ``catalog.safe_voice_dest``
     (``catalog.py:159-188``): ``os.path.basename`` → a ``.wav``/``.mp3``/``.txt`` allow-list
     → a resolved-prefix containment check under ``paths.custom_voices_dir()``; raises
     ``ValueError`` on a disallowed extension or a containment escape.
  2. **Reject-with-a-message (T-05-VAL, the Phase-4 import discipline).** ``validate_clip``
     returns ``(ok, message)`` and NEVER raises — using ``soundfile.info`` (already a dep)
     for duration/samplerate, accepting ~2–12 s incl. sub-24 kHz (16 kHz ``st.audio_input``
     capture — Pitfall 5/7), rejecting a too-short clip / an empty transcript / an
     unreadable format with a clear message.
  3. **Malformed-metadata tolerance (T-05-LBLJSON).** ``list_custom_voices`` tolerates an
     absent/malformed metadata value → falls back to the id, never crashing enumeration
     (the ``voice_labels.get_label_overrides`` idiom).
  4. **Scoped delete + freed bytes (the ``uninstall_piper_voice`` lane).** ``remove_custom_voice``
     blocks an in-use voice (``install_state.voice_in_use`` across the cloning engines +
     any non-terminal job), then ``unlink(missing_ok=True)`` the ``<id>.wav`` + ``<id>.txt``
     scoped to ``custom_voices_dir()`` and clears the metadata key, returning freed bytes.

NO heavy import (D-02/T-05-IMP): stdlib + ``soundfile`` + ``TTSVoice`` only at module top;
``paths`` / ``database`` / ``install_state`` are lazy-imported inside the functions. NEVER
``torch``/``f5_tts`` — those live ONLY in ``heavy_workers/f5_worker.py`` (run by the venv
python). ``soundfile`` is the audio dep Kokoro already uses (WAV I/O), not a heavy SDK.
"""

import json
import logging
import os
import re
import sqlite3
from pathlib import Path

from diana.tts.base import TTSVoice

logger = logging.getLogger(__name__)

# The clone reference-clip bounds (RESEARCH D-13 / Pitfall 7). F5 uses the first ~12 s of
# the reference; below ~1 s there is not enough signal to clone. We ACCEPT 2–12 s as the
# sweet spot, accept a longer clip with a note (F5 truncates to the first ~12 s), and
# REJECT sub-floor clips. Samplerate is NOT gated: ``st.audio_input`` captures 16 kHz and
# F5 resamples internally, so rejecting sub-24 kHz would break in-app capture (Pitfall 5).
_MIN_SECONDS = 1.0
_RECOMMENDED_MAX_SECONDS = 12.0

# The allow-listed extensions for a landed custom-voice file (the ``.onnx`` allow-list
# analog in ``catalog.safe_voice_dest`` — here audio clips + the transcript sidecar).
_ALLOWED_EXTS = (".wav", ".mp3", ".txt")

# The engine-agnostic metadata key prefix (NO engine segment — D-11). Mirrors the
# ``voice.labels.<engine>.<id>`` shape in ``voice_labels`` but pool-wide: ``voice.custom.<id>``.
_META_PREFIX = "voice.custom."

# The cloning engines that may hold a custom voice as their per-engine default (the
# in-use block consults each — a custom voice is engine-agnostic, so any of them may
# reference it). Light engines never use a custom voice.
_CLONING_ENGINES = ("f5", "fish")


def _meta_key(voice_id: str) -> str:
    """The engine-agnostic ``app_settings`` key for a custom voice's metadata (D-11)."""
    return f"{_META_PREFIX}{voice_id}"


def _default_db_path() -> str:
    """The CONFIGURED DB path — ``get_config().storage.database_path``, not ``paths.db_path()``.

    Resolving through the config (rather than the per-user resolver directly) makes this
    module agree with every other caller: ``voice_labels`` and ``install_state`` are always
    HANDED ``config.storage.database_path`` explicitly, so enumeration must read the same DB
    those writes land in. A customized ``storage.database_path`` is therefore honored, and a
    fresh machine whose per-user data dir does not exist yet cannot hand ``sqlite3`` a
    directory-less path. In-app behavior is unchanged: that field's default value already IS
    ``str(paths.db_path())`` (``config.py:76``).

    The ``diana.config`` import stays INSIDE the body deliberately — the ``get_config``
    attribute is then looked up at CALL time, so a test's
    ``monkeypatch.setattr(diana.config, "get_config", ...)`` takes effect (exactly what
    ``test_custom_voices_apptest._tmp_config`` relies on). A module-top import would bind the
    original function once at import time and silently break that seam. It also keeps the
    module import-light, like the lazy ``paths`` imports elsewhere in this file.
    """
    from diana.config import get_config

    return get_config().storage.database_path


def safe_custom_voice_dest(name: str) -> Path:
    """Resolve a SAFE on-disk destination for a custom-voice file (T-05-PATH / V12).

    Copies ``catalog.safe_voice_dest``'s structure exactly (``catalog.py:179-188``),
    swapping the extension allow-list for audio/transcript files:

      1. ``os.path.basename`` strips any directory components (neutralizing ``../`` and
         absolute paths — only the leaf name survives).
      2. An extension allow-list rejects anything not ending in ``.wav``/``.mp3``/``.txt``.
      3. A resolved-prefix containment check confirms the destination still resolves
         INSIDE ``paths.custom_voices_dir()`` — defence-in-depth after the basename strip.

    Returns the safe ``Path`` (under ``custom_voices_dir()``) where the file may be
    written; raises ``ValueError`` on a disallowed extension or a containment escape.
    Pure apart from reading ``paths.custom_voices_dir()`` (lazy import keeps the module
    import-light and lets tests monkeypatch the path). Streamlit-free.
    """
    from diana import paths

    base = os.path.basename(name)  # strip any path components (../, absolute)
    if not base.lower().endswith(_ALLOWED_EXTS):
        raise ValueError("Only .wav, .mp3, and .txt files are accepted.")
    dest_dir = paths.custom_voices_dir()
    dest = dest_dir / base
    if not str(dest.resolve()).startswith(str(dest_dir.resolve())):
        raise ValueError("Invalid filename.")  # traversal/zip-slip blocked
    return dest


def validate_clip(audio_path: str, transcript: str) -> tuple[bool, str]:
    """Validate a reference clip + transcript; return ``(ok, message)``, NEVER raise (D-13).

    The Phase-4 import-rejection discipline (``_import_voice_pair``'s ``(ok, msg)``): bad
    input is REPORTED, never crashed on. Uses ``soundfile.info`` (already a dep) to read
    duration/samplerate WITHOUT decoding the whole file. Rules (RESEARCH Pitfall 5/7):

      - an empty/whitespace transcript is rejected (D-12: the transcript is required);
      - an unreadable / unsupported-format clip is rejected (``soundfile`` raises → caught);
      - a clip shorter than ~1 s is rejected (below the clone floor);
      - a clip of ~2–12 s validates True (the sweet spot);
      - a clip longer than ~12 s validates True WITH a note (F5 uses the first ~12 s);
      - samplerate is NOT gated — 16 kHz ``st.audio_input`` capture is accepted (Pitfall 5).

    Returns ``(ok, message)``; the message is always a non-empty human string.
    """
    if not (transcript or "").strip():
        return False, "Please enter the transcript — the exact words spoken in the clip."

    # soundfile reads the header only (no full decode). ANY failure (corrupt file, junk
    # bytes, unsupported codec, missing file) degrades to a clear rejection — never raises.
    try:
        import soundfile as sf

        info = sf.info(str(audio_path))
        duration = float(info.frames) / float(info.samplerate) if info.samplerate else 0.0
    except Exception as e:  # noqa: BLE001 — the contract is "never raises" (T-05-VAL)
        logger.warning("Custom-voice clip unreadable (%s)", e)
        return False, (
            "That audio file could not be read. Use a .wav or .mp3 clip "
            "(2–12 seconds of clear speech)."
        )

    if duration < _MIN_SECONDS:
        return False, (
            f"The clip is too short ({duration:.1f}s). Use at least "
            f"~2 seconds of clear speech for a good clone."
        )
    if duration > _RECOMMENDED_MAX_SECONDS:
        return True, (
            f"Saved — note the clip is {duration:.0f}s; cloning uses the first "
            f"~{int(_RECOMMENDED_MAX_SECONDS)} seconds."
        )
    return True, f"Looks good ({duration:.1f}s reference clip)."


def _ext_for_src(audio_src) -> str:
    """Derive the audio file extension from the upload source, defaulting to ``.wav``.

    Checks the ``name`` attribute on an ``st.file_uploader`` / ``st.audio_input``
    ``UploadedFile`` (or any object that exposes ``.name``), and on a filesystem
    path (``str`` / ``Path``). Returns the lower-case suffix when it is in the
    allow-list (``.wav``, ``.mp3``), otherwise falls back to ``.wav``.
    """
    name = None
    if hasattr(audio_src, "name"):  # UploadedFile from st.file_uploader
        name = audio_src.name
    elif isinstance(audio_src, (str, Path)):
        name = str(audio_src)
    if name:
        ext = Path(name).suffix.lower()
        if ext in (".wav", ".mp3"):
            return ext
    return ".wav"


def _slug(display_name: str) -> str:
    """A filesystem-safe, lowercase id slug derived from a display name.

    Lowercases, replaces any non-alphanumeric run with a single ``-``, and trims
    leading/trailing ``-``. An empty/punctuation-only name falls back to ``voice`` so a
    valid, contained filename always results (the dedupe in ``save_custom_voice`` then
    appends ``-2``/``-3`` for collisions). Pure / Streamlit-free.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (display_name or "").strip().lower()).strip("-")
    return slug or "voice"


def _unique_id(slug: str) -> str:
    """Dedupe a slug against existing ``<id>.wav`` and ``<id>.mp3`` files.

    The filesystem IS the index (the ``list_installed_piper_voice_ids`` lane), so a new
    voice that would collide with an existing clip (in either supported format) gets a
    numeric suffix. Lazy ``paths`` import keeps the module import-light.
    """
    from diana import paths

    cv_dir = paths.custom_voices_dir()
    candidate = slug
    n = 2
    while any((cv_dir / f"{candidate}{ext}").exists() for ext in (".wav", ".mp3")):
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


def _audio_bytes(audio_src) -> bytes:
    """Read raw clip bytes from a path, a file-like object, or raw ``bytes`` (D-11).

    Accepts the shapes the two input methods produce: a filesystem path string/``Path``
    (the temp clip a test writes, or a server-side path), an ``st.file_uploader`` /
    ``st.audio_input`` ``UploadedFile`` (has ``.getvalue()``), or already-read ``bytes``.
    """
    if isinstance(audio_src, (bytes, bytearray)):
        return bytes(audio_src)
    if hasattr(audio_src, "getvalue"):  # st.file_uploader / st.audio_input
        return audio_src.getvalue()
    return Path(audio_src).read_bytes()


def save_custom_voice(
    db_path: str,
    engine,  # engine-agnostic: accepted for call-site symmetry, NOT used to key storage
    display_name: str,
    audio_src,
    transcript: str,
) -> tuple[bool, str]:
    """Validate then save a named custom voice into the shared pool; ``(ok, msg)`` (D-13/D-14).

    Engine-AGNOSTIC (D-11): ``engine`` is accepted so callers can pass it for symmetry
    with the other CRUD calls, but it is NEVER used to key storage — the clip and metadata
    land in the one shared pool. The flow:

      1. Read the clip bytes (``_audio_bytes``); derive a filesystem-safe, deduped id from
         ``display_name`` (``_slug`` + ``_unique_id``).
      2. Write the clip to ``custom_voices_dir()/<id>.wav`` THROUGH ``safe_custom_voice_dest``
         (basename + allow-list + containment — T-05-PATH), then ``validate_clip`` the
         on-disk file + transcript; on rejection, roll the clip back and return
         ``(False, msg)`` so a rejected clip never lingers (T-05-VAL).
      3. Write the transcript to ``<id>.txt`` and store ``{"name": display_name}`` JSON at
         the engine-agnostic ``voice.custom.<id>``.

    NEVER raises to the UI — a path-safety/IO failure degrades to ``(False, msg)``.
    """
    try:
        raw = _audio_bytes(audio_src)
    except Exception as e:  # noqa: BLE001 — read failure is a rejection, never a crash
        logger.warning("Custom-voice audio read failed (%s)", e)
        return False, "Could not read the audio clip. Try a different .wav or .mp3 file."

    name = (display_name or "").strip()
    if not name:
        return False, "Please give the voice a name."

    voice_id = _unique_id(_slug(name))
    # Preserve the real extension from the upload source so synthesis engines that
    # choose their audio decoder by file extension (F5, Fish) receive the correct
    # format signal.  soundfile.info() reads magic bytes, not the extension, so
    # validation always reflects the actual content regardless of extension.
    clip_ext = _ext_for_src(audio_src)
    try:
        wav_dest = safe_custom_voice_dest(f"{voice_id}{clip_ext}")
        txt_dest = safe_custom_voice_dest(f"{voice_id}.txt")
    except ValueError as e:
        return False, str(e)

    # Land the clip first so validate_clip reads the real on-disk file, then roll it back
    # if validation fails (so a rejected clip never lingers in the library).
    try:
        wav_dest.parent.mkdir(parents=True, exist_ok=True)
        wav_dest.write_bytes(raw)
    except OSError as e:
        logger.warning("Custom-voice write failed (%s)", e)
        return False, "Could not save the audio clip to your library folder."

    ok, msg = validate_clip(str(wav_dest), transcript)
    if not ok:
        wav_dest.unlink(missing_ok=True)  # reject-with-message: leave nothing behind
        return False, msg

    try:
        txt_dest.write_text(transcript.strip(), encoding="utf-8")
    except OSError as e:
        wav_dest.unlink(missing_ok=True)
        logger.warning("Custom-voice transcript write failed (%s)", e)
        return False, "Could not save the transcript to your library folder."

    from diana.database import set_setting

    set_setting(db_path, _meta_key(voice_id), json.dumps({"name": name}))
    return True, f"Saved '{name}'. {msg}"


def _name_for(db_path: str, voice_id: str) -> str:
    """Display name from ``voice.custom.<id>`` metadata, falling back to the id (T-05-LBLJSON).

    Tolerates an absent/empty/malformed JSON value → returns the id rather than raising,
    so a corrupt metadata value can never crash enumeration (the
    ``voice_labels.get_label_overrides`` idiom). An UNOPENABLE or otherwise erroring DB
    (a not-yet-created data dir on a fresh machine, a locked or corrupt file) degrades the
    same way — any ``sqlite3.Error`` falls back to the id, because a database problem must
    never take down a voice list (analog 3, T-05-LBLJSON). ``get_setting`` is imported lazily.
    """
    from diana.database import get_setting

    try:
        raw = get_setting(db_path, _meta_key(voice_id), None)
    except sqlite3.Error as e:
        logger.warning("Custom-voice metadata unreadable for %s (%s); using the id", voice_id, e)
        return voice_id
    if not raw:
        return voice_id
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Malformed custom-voice metadata for %s; using the id", voice_id)
        return voice_id
    if isinstance(parsed, dict) and isinstance(parsed.get("name"), str) and parsed["name"].strip():
        return parsed["name"]
    return voice_id


def list_custom_voices(db_path: str | None = None, engine=None) -> list[TTSVoice]:
    """Every saved custom voice as a ``TTSVoice`` (engine-agnostic, cheap, never crashes).

    Engine-AGNOSTIC (D-11): ``engine`` is accepted for call-site symmetry but ignored —
    one shared pool. The filesystem IS the index (the ``list_installed_piper_voice_ids``
    lane): a cheap ``*.wav`` glob of ``custom_voices_dir()``, each file's stem becoming a
    voice id. The display name comes from ``voice.custom.<id>`` metadata (``_name_for``),
    which tolerates absent/malformed JSON → falls back to the id (T-05-LBLJSON), so a
    corrupt value never crashes enumeration. ``language="en-us"``, ``tier="enhanced"``
    (ranks with the best neural voices), ``tags=("custom",)`` so the cross-engine browser
    can flag it. Returns ``[]`` when the dir does not exist yet. NO heavy import.
    """
    from diana import paths

    db = db_path or _default_db_path()
    cv_dir = paths.custom_voices_dir()
    if not cv_dir.exists():
        return []
    voices: list[TTSVoice] = []
    # Collect all clip files (.wav and .mp3), deduplicated by stem so a voice saved
    # under either extension appears exactly once in the list.
    seen: set[str] = set()
    clips = sorted(cv_dir.glob("*.wav")) + sorted(cv_dir.glob("*.mp3"))
    for clip in sorted(clips, key=lambda p: p.stem):
        vid = clip.stem
        if vid in seen:
            continue
        seen.add(vid)
        voices.append(
            TTSVoice(
                id=vid,
                name=_name_for(db, vid),
                language="en-us",
                gender="unknown",
                tier="enhanced",
                tags=("custom",),
            )
        )
    return voices


def custom_voice_ref(voice_id: str, db_path: str | None = None) -> tuple[str, str]:
    """Return ``(ref_file, ref_text)`` for a custom voice — an engine's clone reference.

    The clip path (``custom_voices_dir()/<id>.<ext>``) plus the saved transcript
    (``<id>.txt`` contents). Probes ``.wav`` then ``.mp3`` so voices saved in either
    format are resolved correctly. Consumed by a cloning engine's ``_resolve_ref``
    (F5 now, Fish in 05-07) to pass the reference out-of-process to the torch venv.
    Raises ``ValueError`` for an unknown id (no clip on disk in any supported format)
    so a stale selection fails legibly rather than synthesizing silence. ``db_path``
    is accepted for symmetry but the reference is purely filesystem (the transcript
    lives beside the clip).
    """
    from diana import paths

    cv_dir = paths.custom_voices_dir()
    txt = cv_dir / f"{voice_id}.txt"
    for ext in (".wav", ".mp3"):
        clip = cv_dir / f"{voice_id}{ext}"
        if clip.exists():
            ref_text = txt.read_text(encoding="utf-8").strip() if txt.exists() else ""
            return str(clip), ref_text
    raise ValueError(f"Unknown custom voice: {voice_id!r}")


def remove_custom_voice(db_path: str, engine, voice_id: str) -> int:
    """Remove a saved custom voice (in-use block → scoped delete → freed bytes) (D-14/D-16).

    Engine-AGNOSTIC (D-11): ``engine`` is accepted for call-site symmetry but the pool is
    shared, so the in-use check consults EVERY cloning engine (``f5`` + ``fish``) plus any
    non-terminal job — a custom voice set as any cloning engine's default, or chosen by a
    pending/in-flight job, is REFUSED (returns 0, deletes nothing) so the user switches
    first (the ``_render_uninstall_control`` block, reusing ``install_state.voice_in_use``).
    Otherwise it ``unlink(missing_ok=True)`` the ``<id>.wav`` + ``<id>.txt`` SCOPED to
    ``custom_voices_dir()`` (basename-joined Paths, never a user path — T-05-PATH), clears
    the ``voice.custom.<id>`` metadata key, and returns the bytes freed (so the UI can show
    reclaimed space — D-16). Mirrors ``install_state.uninstall_piper_voice``. NO heavy import.
    """
    from diana import paths
    from diana.database import set_setting
    from diana.tts.install_state import voice_in_use

    # In-use block across the cloning engines + non-terminal jobs (a custom voice is
    # engine-agnostic, so any cloning engine may hold it as its default).
    for eng in _CLONING_ENGINES:
        if voice_in_use(db_path, eng, voice_id):
            return 0

    cv_dir = paths.custom_voices_dir()
    freed = 0
    # Remove the clip file in whichever supported format it was saved (.wav or .mp3),
    # plus the transcript sidecar.
    for name in (f"{voice_id}.wav", f"{voice_id}.mp3", f"{voice_id}.txt"):
        target = cv_dir / name  # basename-joined, scoped to the per-user dir (T-05-PATH)
        if target.exists():
            freed += target.stat().st_size
        target.unlink(missing_ok=True)

    # Clear the metadata key (set it empty — set_setting has no delete; an empty value
    # reads back as the id via _name_for, and the cleared voice no longer globs anyway).
    set_setting(db_path, _meta_key(voice_id), "")
    return freed
