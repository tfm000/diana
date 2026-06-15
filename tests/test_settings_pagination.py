"""Pure-helper unit tests for the cross-engine browser pagination (Plan 04-06).

The "Browse all voices" cross-engine table filters the FULL merged voice list first,
then slices the current page. The slicing/clamping core is the Streamlit-FREE
``paginate(items, page, page_size) -> (page_items, total, page, n_pages)`` helper,
defined above any module-level ``st.*`` in ``5_Settings.py`` (mirroring the Phase-3
``resolve_selected_voice_id`` / Plan-03 ``_download_action`` precedent). We AST-slice
just that function out of the page source and exec it into a clean namespace so the
real source is exercised without a Streamlit ScriptRunContext.

Coverage: empty list, an exact-fit page, a partial last page, a page clamped beyond
the end, the page-0/negative guard, and the non-positive page-size guard (never a
zero-division).
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PAGE_SRC = (
    Path(__file__).resolve().parent.parent
    / "diana" / "dashboard" / "pages" / "5_Settings.py"
).read_text(encoding="utf-8")

# AST-slice ONLY the pure pagination helper (no module-level st.* executes).
_WANTED = {"paginate"}


def _load_paginate():
    """Exec just ``paginate`` from the page source into a clean namespace.

    ``st`` is stubbed (paginate never calls it; the stub only guarantees the slice can
    never touch a real ScriptRunContext), mirroring ``test_settings_downloads.py``.
    """
    tree = ast.parse(_PAGE_SRC)
    wanted = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in _WANTED
    ]
    assert {n.name for n in wanted} == _WANTED, (
        "page must define a pure `paginate` helper above any module-level st.*"
    )
    module = ast.Module(body=wanted, type_ignores=[])
    ns: dict = {"st": MagicMock()}
    exec(compile(module, str(_PAGE_SRC), "exec"), ns)  # noqa: S102 — trusted in-repo source
    return ns["paginate"]


paginate = _load_paginate()


def test_paginate_empty_list_is_one_empty_page():
    """An empty filtered result is ONE empty page (so the page control stays valid)."""
    page_items, total, page, n_pages = paginate([], page=1, page_size=25)
    assert page_items == []
    assert total == 0
    assert page == 1
    assert n_pages == 1


def test_paginate_exact_fit_first_page():
    """A full first page returns exactly page_size items; total/n_pages are right."""
    items = list(range(120))
    page_items, total, page, n_pages = paginate(items, page=1, page_size=25)
    assert page_items == list(range(0, 25))
    assert total == 120
    assert page == 1
    assert n_pages == 5  # ceil(120 / 25)


def test_paginate_middle_page_slices_correctly():
    """Page 2 of a 120-item list at size 25 is items 25..49."""
    items = list(range(120))
    page_items, total, page, n_pages = paginate(items, page=2, page_size=25)
    assert page_items == list(range(25, 50))
    assert page == 2
    assert n_pages == 5


def test_paginate_partial_last_page():
    """The final page holds the remainder (shorter than page_size)."""
    items = list(range(120))
    page_items, total, page, n_pages = paginate(items, page=5, page_size=25)
    assert page_items == list(range(100, 120))  # 20 items, the remainder
    assert len(page_items) == 20
    assert page == 5
    assert n_pages == 5


def test_paginate_clamps_page_beyond_range_to_last_page():
    """A page past the end (e.g. after a filter shrank the result) snaps to the last."""
    items = list(range(120))
    page_items, total, page, n_pages = paginate(items, page=99, page_size=25)
    assert page == 5, "a page beyond the end clamps to the last page"
    assert page_items == list(range(100, 120)), "and shows the last page's items"
    assert n_pages == 5


def test_paginate_clamps_zero_and_negative_to_first_page():
    """Page 0 and negatives clamp to page 1 (never an empty/negative slice)."""
    items = list(range(120))
    for bad in (0, -1, -100):
        page_items, total, page, n_pages = paginate(items, page=bad, page_size=25)
        assert page == 1, f"page={bad} must clamp to 1"
        assert page_items == list(range(0, 25))


def test_paginate_non_positive_page_size_never_divides_by_zero():
    """A 0/negative page size is treated as 1 (defensive — no ZeroDivisionError)."""
    items = list(range(3))
    for bad_size in (0, -5):
        page_items, total, page, n_pages = paginate(items, page=1, page_size=bad_size)
        assert total == 3
        assert n_pages == 3, "size coerced to 1 -> one item per page"
        assert page_items == [0]


def test_paginate_page_size_larger_than_total_is_one_page():
    """A page size bigger than the result is a single page with everything."""
    items = list(range(10))
    page_items, total, page, n_pages = paginate(items, page=1, page_size=100)
    assert page_items == items
    assert total == 10
    assert n_pages == 1
    assert page == 1
