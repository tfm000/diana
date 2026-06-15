"""Generic, engine-agnostic resumable download/cache layer.

stdlib + requests only — NO piper/kokoro/onnx/streamlit import (D-19: reused by
Piper voices + the Kokoro model now, heavy engines in Phase 5). It is consumed by
both engines and by the UI download thread, but imports neither — exactly how
``native_os_engine`` keeps winrt/streamlit off the module top.

Download flow: resume via HTTP ``Range`` -> stream into ``{dest}.part`` ->
md5-verify the completed part against the manifest digest -> atomic
``os.replace`` into place. A disk-space pre-check (``has_space``) gates every
download before a byte is written (D-05); ``clean_partials`` bulk-removes orphaned
``.part`` files (D-18 substrate).

Two pitfalls are handled deliberately (both verified live against HuggingFace):
  1. The first GET / a HEAD-through-redirect can report ``Content-Length: 0``;
     the reliable total is the manifest ``size_bytes`` or the ``Content-Range``
     header on a 206. Never trust a zero Content-Length.
  2. A proxy/CDN may ignore ``Range`` and answer 200 instead of 206; appending to
     the existing ``.part`` would then duplicate the prefix and corrupt the file.
     Append ("ab") only on 206; reset the offset and rewrite ("wb") on 200.
"""

import hashlib
import logging
import os
import shutil
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def download_file(url: str, dest: Path, expected_md5: str | None = None,
                  expected_size: int | None = None,
                  progress=None, cancel=None) -> None:
    """Resumable streaming download. progress(downloaded, total); cancel() -> bool.

    Resumes from an existing ``{dest}.part`` via a ``Range`` request: a 206 appends
    the streamed tail, a 200 (server ignored Range) rewrites the part from scratch
    (Pitfall 2). When ``expected_md5`` is given, the completed part is hashed and a
    mismatch deletes the part and raises ValueError (the file is never installed —
    a resumed-from-corruption file will not self-heal). A verified part is moved
    into place with an atomic same-filesystem ``os.replace``. A truthy ``cancel()``
    mid-stream returns early, leaving the ``.part`` intact for a later resume
    (D-06/D-07).
    """
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    offset = part.stat().st_size if part.exists() else 0

    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        # The reliable total: manifest size_bytes first, else the Content-Range on a
        # 206 ("bytes 1000-4884/4885" -> 4885), else Content-Length + offset. Never
        # trust a HEAD/first-GET Content-Length of 0 (Pitfall 1).
        total = expected_size
        cr = r.headers.get("Content-Range")
        if total is None and cr and "/" in cr:
            total = int(cr.rsplit("/", 1)[-1])
        if total is None:
            total = int(r.headers.get("Content-Length", 0)) + offset

        mode = "ab" if offset and r.status_code == 206 else "wb"
        if mode == "wb":
            offset = 0  # server ignored Range (200); restart cleanly (Pitfall 2)
        with open(part, mode) as f:
            downloaded = offset
            for block in r.iter_content(chunk_size=1 << 16):  # 64 KB streaming write
                if cancel and cancel():
                    return  # D-07: leave .part in place for Resume (D-06)
                f.write(block)
                downloaded += len(block)
                if progress:
                    progress(downloaded, total)

    if expected_md5:
        actual = hashlib.md5(part.read_bytes()).hexdigest()
        if actual != expected_md5:
            part.unlink(missing_ok=True)  # corrupt — drop it, do not install
            raise ValueError(
                f"md5 mismatch for {dest.name}: {actual} != {expected_md5}")
    os.replace(part, dest)  # atomic on the same filesystem (POSIX + Windows)


def has_space(target: Path, needed_bytes: int, margin: float = 1.10) -> tuple[bool, int]:
    """Return (ok, free_bytes). margin reserves headroom over the raw need (D-05).

    The target subdir may not exist yet (a fresh ``model_dir()``), so walk up to the
    first existing ancestor — ``shutil.disk_usage`` needs an existing path.
    """
    p = target
    while not p.exists():
        p = p.parent
    free = shutil.disk_usage(p).free
    return free >= int(needed_bytes * margin), free


def clean_partials(directory: "Path | None" = None) -> int:
    """Remove every orphaned ``*.part`` file in ``directory``; return the count (D-18).

    ``directory`` defaults to the per-user model cache (``paths.model_dir()``) so the
    bulk "Clean up partial downloads" action (D-18) is a zero-arg call; pass an
    explicit directory to clean any other location. ``paths`` is imported lazily so
    this engine-agnostic module keeps a minimal top-of-file import surface (D-19).
    Mirrors the ``unlink(missing_ok=True)`` cleanup idiom in ``database.delete_job``.
    """
    if directory is None:
        from diana import paths
        directory = paths.model_dir()
    removed = 0
    for p in Path(directory).glob("*.part"):
        p.unlink(missing_ok=True)
        removed += 1
    return removed
