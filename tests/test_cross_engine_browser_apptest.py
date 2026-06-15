"""Interaction-level AppTest checks for the paginated cross-engine voice browser (04-06).

The 04-06 human-verify checkpoint found the "Browse all voices" cross-engine section
unusable: ~184 native_os + Kokoro + Piper voices rendered all at once. It was replaced
with a PAGINATED READ-ONLY TABLE (``st.dataframe``) + a select-to-edit panel. These
drive the REAL Settings ▸ Voices flow through ``st.testing.v1.AppTest`` and assert on
the resulting table/widgets — the standing post-Phase-4 interaction-level requirement
(shallow "renders without exception" tests missed real logic bugs at earlier
checkpoints). They cover the load-bearing behaviors:

  * Filter applies across the FULL dataset (not just the visible page): an engine /
    language filter changes the table's TOTAL count and no non-matching row appears on
    ANY page.
  * Pagination slices correctly: 120 voices @ size 25 -> page 1 shows 25 ("Showing
    1–25 of 120"); page 2 shows the next 25; the last page shows the remainder.
  * Page-size change (25 -> 100) resets to page 1 and shows up to 100.
  * Filter change resets to page 1 (navigate to page 3, then change the search).
  * Select-to-edit: select a voice, save a tag override -> it persists to app_settings
    and the voice is then findable via the search filter.

Everything is deterministic and OFFLINE: ``paths.model_dir``/``voices_dir`` are
monkeypatched to ``tmp_path``, the config singleton points at a tmp sqlite DB, and the
cross-engine enumerator is stubbed to a known >100-voice multi-engine set so no real
``say -v '?'`` shell or network/Kokoro work runs.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

import diana.config as C
import diana.dashboard.voice_cache as VC
import diana.paths as P
from diana.database import get_setting, init_db
from diana.tts.base import TTSVoice

try:
    from streamlit.testing.v1 import AppTest
    _APPTEST = True
except ImportError:  # pragma: no cover - AppTest ships with the pinned Streamlit
    _APPTEST = False

pytestmark = pytest.mark.skipif(not _APPTEST, reason="streamlit AppTest unavailable")

_PAGE = str(
    Path(__file__).resolve().parent.parent
    / "diana" / "dashboard" / "pages" / "5_Settings.py"
)


def _build_pairs():
    """A deterministic >100-voice cross-engine set spanning three engines + languages.

    120 voices total, partitioned so engine and language filters are independently
    testable against the FULL dataset:

      * 60 piper   voices, language ``en-us`` (ids ``piper-en-000``..``piper-en-059``)
      * 40 native_os voices, language ``fr-fr`` (ids ``nat-fr-000``..``nat-fr-039``)
      * 20 kokoro  voices, language ``de-de`` (ids ``kok-de-000``..``kok-de-019``)

    All ``standard`` tier so ``order_by_quality`` is a stable no-op (the slice order is
    then the build order — predictable for the pagination assertions).
    """
    pairs = []
    for i in range(60):
        pairs.append((
            "piper",
            TTSVoice(f"piper-en-{i:03d}", f"Piper Voice {i:03d}", "en-us", "female"),
        ))
    for i in range(40):
        pairs.append((
            "native_os",
            TTSVoice(f"nat-fr-{i:03d}", f"Native Voice {i:03d}", "fr-fr", "male"),
        ))
    for i in range(20):
        pairs.append((
            "kokoro",
            TTSVoice(f"kok-de-{i:03d}", f"Kokoro Voice {i:03d}", "de-de", "female"),
        ))
    return pairs


def _run_app(monkeypatch, tmp_path, *, pairs=None):
    """Build + run the Settings page under AppTest, fully offline/deterministic.

    Mirrors ``test_uninstall_apptest._run_app``: points ``model_dir``/``voices_dir`` at
    tmp, the config singleton at a tmp DB, stubs the cached enumerators (so no OS shell /
    network), and replaces ``clear_voice_cache`` with a Mock. Returns ``(at, db_path)``
    with ``at`` already run.
    """
    model_dir = tmp_path / "models"
    model_dir.mkdir(exist_ok=True)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir(exist_ok=True)
    db_path = str(tmp_path / "diana.db")
    init_db(db_path)

    cfg = C.load_config()
    cfg.storage.database_path = db_path
    # Keep the General tab on native_os so its Default-Voice picker does not persist a
    # piper default (irrelevant to the cross-engine browser, but keeps the page quiet).
    cfg.tts.engine = "native_os"

    all_pairs = pairs if pairs is not None else _build_pairs()
    # The General tab calls cached_voices(engine); give it a tiny native_os list so that
    # tab renders without a real ``say`` shell (the browser uses cached_all_engine_voices).
    nat_voices = [v for e, v in all_pairs if e == "native_os"][:3]

    monkeypatch.setattr(P, "model_dir", lambda: model_dir)
    monkeypatch.setattr(P, "voices_dir", lambda: voices_dir)
    monkeypatch.setattr(C, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(VC, "get_config", lambda *a, **k: cfg)
    monkeypatch.setattr(VC, "cached_voices", lambda engine: list(nat_voices))
    monkeypatch.setattr(VC, "cached_all_engine_voices", lambda: list(all_pairs))
    monkeypatch.setattr(VC, "clear_voice_cache", Mock(name="clear_voice_cache"))

    at = AppTest.from_file(_PAGE, default_timeout=30)
    at.run()
    assert at.exception is None or len(at.exception) == 0, f"page raised: {at.exception}"
    return at, db_path


# --- widget accessors (target by key — the page has many widgets) ------------
def _sel(at, key):
    for s in at.selectbox:
        if s.key == key:
            return s
    return None


def _txt(at, key):
    for t in at.text_input:
        if t.key == key:
            return t
    return None


def _num(at, key):
    for n in at.number_input:
        if n.key == key:
            return n
    return None


def _table(at):
    """The cross-engine read-only dataframe as a list[dict] of row records.

    The browser renders exactly ONE ``st.dataframe`` (the cross-engine table); return
    its rows so assertions can read engine/id columns. Empty list if no table rendered.
    """
    if not at.dataframe:
        return []
    return at.dataframe[0].value.to_dict("records")


def _caption_text(at):
    return " || ".join(str(c.value) for c in at.caption)


# --- Filter applies across the FULL dataset ---------------------------------
def test_engine_filter_spans_full_dataset_not_just_visible_page(monkeypatch, tmp_path):
    """Engine=piper -> the TOTAL count is the full 60-voice piper set; NO other engine
    appears on the current page (the filter ran over everything, then sliced)."""
    at, _db = _run_app(monkeypatch, tmp_path)

    engine = _sel(at, "xe_engine")
    assert engine is not None, "the cross-engine browser offers an Engine filter"
    engine.set_value("piper").run()

    # The "Showing X–Y of N voices" caption reflects the FULL filtered total (60),
    # proving the filter applied to the whole dataset, not just one page.
    assert _has_caption(at, "of 60 voices"), \
        f"engine=piper must filter the full dataset to 60; captions={_caption_text(at)!r}"
    # The visible page shows only piper rows (page size 25 -> 25 rows, all piper).
    rows = _table(at)
    assert rows, "a filtered table still renders rows"
    assert all(r["Engine"] == "piper" for r in rows), \
        "no non-piper engine may appear once Engine=piper is selected"


def test_language_filter_spans_full_dataset(monkeypatch, tmp_path):
    """Language=fr-fr -> the TOTAL is the 40 native_os fr-fr voices; no en/de row shows."""
    at, _db = _run_app(monkeypatch, tmp_path)

    lang = _sel(at, "xe_lang")
    assert lang is not None, "the cross-engine browser offers a Language filter"
    lang.set_value("fr-fr").run()

    assert _has_caption(at, "of 40 voices"), \
        f"language=fr-fr must filter the full dataset to 40; captions={_caption_text(at)!r}"
    rows = _table(at)
    assert all(r["Language"] == "fr-fr" for r in rows), \
        "no non-fr-fr language may appear once Language=fr-fr is selected"
    assert all(r["Engine"] == "native_os" for r in rows), \
        "the fr-fr voices are all native_os in this fixture"


def test_no_nonmatching_engine_on_any_page(monkeypatch, tmp_path):
    """With Engine=piper, walk EVERY page and confirm no non-piper row ever appears."""
    at, _db = _run_app(monkeypatch, tmp_path)
    _sel(at, "xe_engine").set_value("piper").run()

    # 60 piper voices @ size 25 -> 3 pages. Visit each and assert engine purity + count.
    seen_ids = set()
    for pg in (1, 2, 3):
        page = _num(at, "xeng_page")
        assert page is not None, "a multi-page filtered result offers a page control"
        page.set_value(pg).run()
        rows = _table(at)
        assert all(r["Engine"] == "piper" for r in rows), f"page {pg} leaked a non-piper row"
        seen_ids |= {r["Voice ID"] for r in rows}
    assert len(seen_ids) == 60, "every piper voice is reachable across the pages"


# --- Pagination slices correctly --------------------------------------------
def test_pagination_first_page_shows_25_of_120(monkeypatch, tmp_path):
    """Default size 25 over 120 voices: page 1 shows 25 rows + 'Showing 1–25 of 120'."""
    at, _db = _run_app(monkeypatch, tmp_path)

    rows = _table(at)
    assert len(rows) == 25, "the default page shows page_size (25) rows"
    assert _has_caption(at, "Showing 1–25 of 120"), \
        f"the caption reports the page window + full total; captions={_caption_text(at)!r}"


def test_pagination_second_page_shows_next_25(monkeypatch, tmp_path):
    """Navigating to page 2 slices items 26..50 ('Showing 26–50 of 120')."""
    at, _db = _run_app(monkeypatch, tmp_path)
    first_ids = {r["Voice ID"] for r in _table(at)}

    _num(at, "xeng_page").set_value(2).run()
    second = _table(at)
    assert len(second) == 25, "page 2 shows the next 25"
    assert _has_caption(at, "Showing 26–50 of 120"), \
        f"page-2 caption reports the new window; captions={_caption_text(at)!r}"
    second_ids = {r["Voice ID"] for r in second}
    assert first_ids.isdisjoint(second_ids), "page 2 holds different voices than page 1"


def test_pagination_last_page_shows_remainder(monkeypatch, tmp_path):
    """The last page holds the remainder. 120 @ 25 -> 5 pages; page 5 shows 20 rows."""
    at, _db = _run_app(monkeypatch, tmp_path)
    _num(at, "xeng_page").set_value(5).run()

    rows = _table(at)
    assert len(rows) == 20, "the last page shows the 20-voice remainder"
    assert _has_caption(at, "Showing 101–120 of 120"), \
        f"the last-page window is reported; captions={_caption_text(at)!r}"


# --- Page-size change resets to page 1 --------------------------------------
def test_page_size_change_resets_to_first_page_and_shows_up_to_100(monkeypatch, tmp_path):
    """Change size 25 -> 100: snaps back to page 1 and shows up to 100 rows."""
    at, _db = _run_app(monkeypatch, tmp_path)
    # Go to page 3 first so the reset is observable.
    _num(at, "xeng_page").set_value(3).run()
    assert _num(at, "xeng_page").value == 3

    _sel(at, "xeng_page_size").set_value(100).run()
    rows = _table(at)
    assert len(rows) == 100, "size 100 shows up to 100 rows on the page"
    assert _has_caption(at, "Showing 1–100 of 120"), \
        f"a page-size change resets to page 1; captions={_caption_text(at)!r}"
    # The page control (now 2 pages: 100 + 20) is back on page 1.
    page = _num(at, "xeng_page")
    if page is not None:
        assert page.value == 1, "page resets to 1 after a page-size change"


# --- Filter change resets to page 1 -----------------------------------------
def test_filter_change_resets_to_first_page(monkeypatch, tmp_path):
    """Navigate to page 3, then change the search -> back on page 1, filtered."""
    at, _db = _run_app(monkeypatch, tmp_path)
    _num(at, "xeng_page").set_value(3).run()
    assert _num(at, "xeng_page").value == 3, "precondition: on page 3"

    # Search 'Piper Voice 01' matches piper-en-010..019 (10 voices) -> 1 page.
    _txt(at, "xe_search").set_value("Piper Voice 01").run()

    rows = _table(at)
    assert rows, "the search matches some voices"
    assert all(r["Name"].startswith("Piper Voice 01") for r in rows), \
        "the table shows only the searched voices (filter applied to the full set)"
    # Back on page 1: the window starts at 1.
    assert _has_caption(at, "Showing 1–"), \
        f"a filter change resets to page 1; captions={_caption_text(at)!r}"


# --- Select-to-edit persists + becomes searchable ---------------------------
def test_select_to_edit_saves_tag_and_voice_becomes_searchable(monkeypatch, tmp_path):
    """Select a voice, save a custom tag -> it persists to app_settings, and the voice
    is then findable via the name/tag search filter (overrides feed the filters)."""
    at, db_path = _run_app(monkeypatch, tmp_path)

    # Pick a known voice in the select-to-edit panel (options span the FULL filtered set).
    edit = _sel(at, "xeng_edit_select")
    assert edit is not None, "the browser offers a 'Select a voice to edit labels' picker"
    # Label format is "{engine} · {name} ({id})" — choose a specific piper voice.
    target_label = "piper · Piper Voice 005 (piper-en-005)"
    assert target_label in edit.options, \
        f"the select-to-edit options span the filtered set; got e.g. {edit.options[:3]}"
    edit.set_value(target_label).run()

    # The existing 04-05 label editor now renders for that voice; set a custom tag + save.
    tags = _txt(at, "lbl_tags_piper:piper-en-005")
    assert tags is not None, "selecting a voice opens the existing label/tag editor"
    tags.set_value("audiobookzz").run()
    save = None
    for b in at.button:
        if b.key == "lbl_save_piper:piper-en-005":
            save = b
            break
    assert save is not None, "the editor offers a Save labels button"
    save.click().run()

    # Persisted to app_settings under voice.labels.piper.piper-en-005 (JSON w/ the tag).
    raw = get_setting(db_path, "voice.labels.piper.piper-en-005", None)
    assert raw is not None and "audiobookzz" in raw, \
        f"the saved tag persists to app_settings; stored={raw!r}"

    # The override now feeds the filters: searching the custom tag finds the voice. The
    # stubbed cached_all_engine_voices returns the same base list each run; apply_overrides
    # reads the just-written app_settings, so the tag is live on the next run's search.
    _txt(at, "xe_search").set_value("audiobookzz").run()
    rows = _table(at)
    assert any(r["Voice ID"] == "piper-en-005" for r in rows), \
        "the relabeled voice is found by its new custom tag (overrides feed the search)"
    assert "audiobookzz" in rows[0]["Tags"], "the table shows the merged custom tag"


# --- A tiny shared caption matcher (defined late so the tests above read top-down) ---
def _has_caption(at, needle):
    return any(needle in str(c.value) for c in at.caption)
