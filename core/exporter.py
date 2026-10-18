"""Playwright exporter for card document sheets to PDF."""

from pathlib import Path

from playwright.sync_api import sync_playwright


def export_pdf(html_path: str | Path, pdf_path: str | Path) -> None:
    """Render an HTML file into an A4 borderless PDF using headless Chromium."""
    abs_html = Path(html_path).resolve().as_uri()
    dest_pdf = Path(pdf_path).resolve()
    dest_pdf.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(abs_html, wait_until="networkidle")
        page.pdf(
            path=str(dest_pdf),
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )
        browser.close()
