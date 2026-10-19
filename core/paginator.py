"""Card pagination and sheet packing utilities."""

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

CHECK_OVERFLOW_JS = """
() => {
    const tolerance = 1.0;
    for (const body of document.querySelectorAll('.card-body')) {
        if (body.scrollHeight - body.clientHeight > tolerance) return true;

        const last = body.lastElementChild;
        if (last && last.getBoundingClientRect().bottom - body.getBoundingClientRect().bottom > tolerance) {
            return true;
        }
    }
    return false;
}
"""

STYLES_LOADED_JS = """
() => {
    const card = document.querySelector('.card');
    if (!card) return true;
    return getComputedStyle(card).overflow === 'hidden';
}
"""

_PREVIEW_FILE = Path(tempfile.gettempdir()) / "dnd_cards_preview.html"


def load_preview(page: Page, html_doc: str) -> None:
    """Load a preview from a real file:// URL so local stylesheets are allowed to load."""
    _PREVIEW_FILE.write_text(html_doc, encoding="utf-8")
    page.goto(_PREVIEW_FILE.as_uri(), wait_until="load")
    if not page.evaluate(STYLES_LOADED_JS):
        raise RuntimeError("Preview CSS was not applied; overflow detection would be unreliable.")


def paginate_cards(
    items: list[Any],
    render_card_fn: Callable[[Any], str],
    per_page: int = 9,
) -> list[str]:
    """
    Chunk cards into A4 sheets containing up to `per_page` cards each.
    Returns a list of HTML strings representing individual <div class="sheet"> pages.
    """
    sheets: list[str] = []
    for i in range(0, len(items), per_page):
        batch = items[i : i + per_page]
        cards_html = "\n".join(render_card_fn(item) for item in batch)
        sheets.append(f'<div class="sheet">\n{cards_html}\n</div>')
    return sheets


def render_preview_document(cards_html: str, css_path: Path) -> str:
    css_uri = css_path.resolve().as_uri()
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="{css_uri}">
</head>
<body>
    <div class="sheet">{cards_html}</div>
</body>
</html>"""


def can_pack_into_k_cards(
    item: dict,
    units: list[str],
    k: int,
    page: Page,
    css_path: Path,
    build_candidate_fn: Callable[[dict, list, int, int], dict],
    render_card_fn: Callable[[dict[str, Any]], str],
    overflow_js: str = CHECK_OVERFLOW_JS,
) -> list[dict] | None:
    """Attempts to distribute text units across at most k cards.
    Returns the list of subcards if successful, or None if it cannot fit."""
    subcards: list[dict] = []
    unit_idx = 0
    total_units = len(units)

    for card_num in range(1, k + 1):
        current_units: list[str] = []

        while unit_idx < total_units:
            candidate_unit = units[unit_idx]
            test_units = current_units + [candidate_unit]
            test_item = build_candidate_fn(item, test_units, card_num, k)
            test_html = render_preview_document(render_card_fn(test_item), css_path)
            load_preview(page, test_html)

            if page.evaluate(overflow_js):
                # Candidate unit does not fit on this card
                break
            else:
                current_units.append(candidate_unit)
                unit_idx += 1

        if not current_units:
            # Not even a single unit could fit
            return None

        part_item = build_candidate_fn(item, current_units, card_num, k)
        subcards.append(part_item)

        if unit_idx >= total_units:
            return subcards

    return None if unit_idx < total_units else subcards
