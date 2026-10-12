import argparse
import html
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright


CLASS_ABBREVIATIONS: dict[str, str] = {
    "bárbaro": "BÁR",
    "bardo": "BRD",
    "brujo": "BRJ",
    "clérigo": "CLÉ",
    "druida": "DRU",
    "explorador": "EXP",
    "guerrero": "GUE",
    "hechicero": "HEC",
    "mago": "MAG",
    "monje": "MON",
    "paladín": "PAL",
    "pícaro": "PÍC",
}


def abbreviate_class(name: str) -> str:
    cleaned = name.strip()
    return CLASS_ABBREVIATIONS.get(cleaned.lower(), cleaned)


def bold_paragraph_lead(text: str) -> str:
    """
    Bolds leading label-like sentences at the start of a paragraph, 
    such as 'Combate.', 'Conexión telepática.', or 'Un solo familiar.'.
    Matches 1 to 5 words followed by a dot, as long as it's not a common abbreviation.
    """
    # Exclude common non-heading prefixes if needed (e.g. 'Por último.')
    pattern = r"^((?:[A-ZÁÉÍÓÚÑ][\w\-\']*(?:\s+[\w\-\']+){0,4})\.)\s+"
    
    # Optional list of phrases you don't want bolded even if they match
    skip_leads = {"Por último."}
    
    match = re.match(pattern, text)
    if match:
        lead = match.group(1)
        if lead not in skip_leads:
            rest = text[match.end():]
            return f"<strong>{lead}</strong> {rest}"
    return text


def extract_level_and_school(spell: dict) -> tuple[str, str, str]:
    raw_level = str(spell.get("level", "")).strip()
    school = str(spell.get("school", "")).strip().capitalize()

    if raw_level.lower() == "cantrip" or raw_level == "0":
        level_str = "0"
        higher_label = "Mejora de truco."
    else:
        level_str = raw_level
        higher_label = "A niveles superiores."

    return level_str, school, higher_label


def split_text_units(description: str, higher_level: str, higher_label: str) -> list[str]:
    """Splits description into units while preserving list items and paragraph breaks."""
    lines = [line.strip() for line in str(description).split("\n") if line.strip()]
    units: list[str] = []

    for line in lines:
        is_bullet = line.startswith(("•", "-", "*"))
        if is_bullet:
            units.append(line)
            units.append("__BREAK__")
        else:
            sentences = re.split(r"(?<=[.!?])\s+", line)
            for s in sentences:
                if s.strip():
                    units.append(s.strip())
            units.append("__BREAK__")

    if units and units[-1] == "__BREAK__":
        units.pop()

    if higher_level:
        units.append(f"__HIGHER__<strong>{html.escape(higher_label)}</strong> {html.escape(str(higher_level))}")

    return units


def build_card_html(spell: dict, card_title: str | None = None) -> str:
    raw_title = card_title or spell.get("display_title") or spell.get("name", "")
    name = html.escape(str(raw_title))

    # Detect if it's a continuation card (e.g.: "Spell Name (2/2)")
    is_continuation = bool(re.search(r"\((?:[2-9]|\d{2,})/\d+\)$", name))

    casting_time = html.escape(str(spell.get("casting_time", "")))
    range_area = html.escape(str(spell.get("range_area", "")))
    duration = html.escape(str(spell.get("duration", "")))
    description = spell.get("description", "")
    higher_level = spell.get("higher_level", "")
    materials = spell.get("material", "")

    # Check ritual flag
    is_ritual = bool(spell.get("ritual", False))
    ritual_badge = '<span class="ritual-badge" title="Ritual">R</span>' if is_ritual else ""

    # Calculate approximate text volume to scale font sizes dynamically
    text_volume = len(str(description)) + len(str(higher_level)) + len(str(materials))

    # Assign scaling classes (skip scaling for continuation cards as they are usually packed)
    if is_continuation:
        body_class = "card-body"
    elif text_volume < 420:
        body_class = "card-body text-large"
    elif text_volume < 630:
        body_class = "card-body text-medium"
    else:
        body_class = "card-body"

    # Schema components: array of strings e.g. ["V", "S"]
    components_list = spell.get("components", [])
    components = html.escape(", ".join(components_list))

    level_str, school_type, higher_label = extract_level_and_school(spell)

    # Schema tags: array of strings representing classes
    tags_list = spell.get("tags", [])
    full_classes_str = ", ".join(tags_list)
    abbreviated_classes = [abbreviate_class(cls_name) for cls_name in tags_list]
    spell_classes = html.escape(", ".join(abbreviated_classes))

    # Optional icon
    icon_url = spell.get("icon")
    if icon_url:
        icon_html = f'<img src="{html.escape(icon_url)}" class="header-icon-img" alt="" />'
    else:
        icon_html = '<div class="header-icon-placeholder"></div>'

    # Schema attack_save & damage_effect combined banner
    attack_val = spell.get("attack_save")
    damage_val = spell.get("damage_effect")
    attack_combined = ""
    if attack_val and damage_val:
        attack_combined = f"{attack_val} ({damage_val})"
    elif attack_val:
        attack_combined = str(attack_val)
    elif damage_val:
        attack_combined = str(damage_val)

    attack_html = ""
    if attack_combined:
        attack_html = f"""
        <div class="meta-item meta-fullwidth">
            <span class="meta-label">ATAQUE / SALVACIÓN</span>
            <span class="meta-value">{html.escape(attack_combined)}</span>
        </div>
        """

    materials_html = (
        f'<div class="materials">{html.escape(materials)}</div>'
        if materials
        else ""
    )

    # Only generate metadata block if it's the first card
    if is_continuation:
        header_html = f"""
        <header class="card-header header-continuation">
            <h1 class="card-title">{name}</h1>
            <div class="hexagon-box">
                <svg viewBox="0 0 24 24" class="hex-svg">
                    <polygon points="12,1.5 22,7 22,17 12,22.5 2,17 2,7" class="hex-polygon" />
                    <text x="12" y="13.5" text-anchor="middle" dominant-baseline="middle" class="hex-text">{level_str}</text>
                </svg>
                {ritual_badge}
            </div>
        </header>
        """
        meta_html = ""
    else:
        header_html = f"""
        <header class="card-header">
            <div class="header-icon-box">
                {icon_html}
            </div>
            <h1 class="card-title">{name}</h1>
            <div class="hexagon-box">
                <svg viewBox="0 0 24 24" class="hex-svg">
                    <polygon points="12,1.5 22,7 22,17 12,22.5 2,17 2,7" class="hex-polygon" />
                    <text x="12" y="13.5" text-anchor="middle" dominant-baseline="middle" class="hex-text">{level_str}</text>
                </svg>
                {ritual_badge}
            </div>
        </header>
        """
        meta_html = f"""
        <div class="meta-grid">
            <div class="meta-item">
                <span class="meta-label">TIEMPO DE LANZAMIENTO</span>
                <span class="meta-value">{casting_time}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">ALCANCE</span>
                <span class="meta-value">{range_area}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">COMPONENTES</span>
                <span class="meta-value">{components}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">DURACIÓN</span>
                <span class="meta-value">{duration}</span>
            </div>
            {attack_html}
        </div>
        {materials_html}
        """

    # Reconstruct paragraphs and sentences
    raw_lines = str(description).split("\n")
    paragraphs: list[str] = []
    current_p_sentences: list[str] = []

    def flush_sentences():
        if current_p_sentences:
            full_text = bold_paragraph_lead(" ".join(current_p_sentences))
            paragraphs.append(f"<p>{full_text}</p>")
            current_p_sentences.clear()

    for line in raw_lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean == "__BREAK__":
            flush_sentences()
        elif line_clean.startswith("__HIGHER__"):
            flush_sentences()
            paragraphs.append(f'<p class="higher-levels">{line_clean.removeprefix("__HIGHER__")}</p>')
        elif line_clean.startswith(("•", "-", "*")):
            flush_sentences()
            paragraphs.append(f'<p class="bullet-item">{html.escape(line_clean)}</p>')
        else:
            current_p_sentences.append(html.escape(line_clean))

    flush_sentences()

    if higher_level and not any("__HIGHER__" in line for line in raw_lines):
        paragraphs.append(f'<p class="higher-levels"><strong>{html.escape(higher_label)}</strong> {html.escape(str(higher_level))}</p>')

    desc_html = "".join(paragraphs)

    footer_class = "card-footer footer-continuation" if is_continuation else "card-footer"

    # Format book and page reference (e.g., "PHB: 276" -> "PHB#276")
    source_obj = spell.get("source")
    source_text = source_obj.get("text", "").strip() if source_obj else ""

    source_html = ""
    if source_text:
        # Replace ": " or ":" with "#"
        formatted_source = re.sub(r":\s*", "#", source_text)
        source_html = f'<div class="card-source">{html.escape(formatted_source)}</div>'

    return f"""
    <div class="card">
        <div class="card-inner">
            {header_html}
            {meta_html}

            <div class="{body_class}">
                {desc_html}
            </div>

            <footer class="{footer_class}">
                <span class="footer-classes" title="{html.escape(full_classes_str)}">{spell_classes}</span>
                <span class="footer-type">{html.escape(school_type)}</span>
            </footer>
        </div>
        {source_html}
    </div>
    """


def render_preview_document(cards_html: str, css_path: Path) -> str:
    css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>{css_content}</style>
</head>
<body>
    <div class="sheet">{cards_html}</div>
</body>
</html>"""


CHECK_OVERFLOW_JS = """
() => {
    const body = document.querySelector('.card-body');
    if (!body) return false;
    return (body.scrollHeight - body.clientHeight) > 8.0;
}
"""


def can_pack_into_k_cards(units: list[str], k: int, spell: dict, page, css_path: Path) -> list[dict] | None:
    """Attempts to distribute text units across at most k cards. 
    Returns the list of subcards if successful, or None if it cannot fit."""
    base_name = spell.get("name", "")
    subcards: list[dict] = []
    unit_idx = 0
    total_units = len(units)

    for card_num in range(1, k + 1):
        current_units: list[str] = []
        mock_title = f"{base_name} ({card_num}/{k})" if k > 1 else base_name

        while unit_idx < total_units:
            candidate_unit = units[unit_idx]
            test_units = current_units + [candidate_unit]

            candidate_spell = dict(spell)
            candidate_spell["description"] = "\n".join(test_units)
            candidate_spell["higher_level"] = ""
            candidate_spell["display_title"] = mock_title

            test_html = render_preview_document(build_card_html(candidate_spell), css_path)
            page.set_content(test_html, wait_until="load")

            if page.evaluate(CHECK_OVERFLOW_JS):
                # Candidate unit does not fit on this card
                break
            else:
                current_units.append(candidate_unit)
                unit_idx += 1

        if not current_units:
            # Not even a single unit could fit
            return None

        part_spell = dict(spell)
        part_spell["description"] = "\n".join(current_units)
        part_spell["higher_level"] = ""
        part_spell["display_title"] = mock_title
        subcards.append(part_spell)

        if unit_idx >= total_units:
            return subcards

    return None if unit_idx < total_units else subcards


def split_overflowing_spells(spells: list[dict], css_filename: str) -> list[dict]:
    css_path = Path(css_filename).resolve()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(device_scale_factor=2)
        page = context.new_page()
        page.emulate_media(media="print")

        processed_cards: list[dict] = []

        for spell in spells:
            test_html = render_preview_document(build_card_html(spell), css_path)
            page.set_content(test_html, wait_until="load")

            # Fits on a single regular card
            if not page.evaluate(CHECK_OVERFLOW_JS):
                processed_cards.append(spell)
                continue

            _, _, higher_label = extract_level_and_school(spell)
            units = split_text_units(
                spell.get("description", ""),
                spell.get("higher_level", ""),
                higher_label,
            )

            # Try to pack into minimal number of cards: 2, then 3, etc.
            packed_cards = None
            for target_k in range(2, 6):
                packed_cards = can_pack_into_k_cards(units, target_k, spell, page, css_path)
                if packed_cards is not None:
                    break

            if packed_cards:
                processed_cards.extend(packed_cards)
            else:
                processed_cards.append(spell)

        browser.close()

    return processed_cards


def generate_html(spells: list[dict], css_filename: str = "styles.css", printable: bool = False) -> str:
    pages = []
    for i in range(0, len(spells), 9):
        batch = spells[i : i + 9]
        cards = "\n".join(build_card_html(s, card_title=s.get("display_title")) for s in batch)
        pages.append(f'<div class="sheet">\n{cards}\n</div>')

    pages_html = "\n".join(pages)
    printable_class = " printable" if printable else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Cartas de Conjuros</title>
<link rel="stylesheet" href="{html.escape(css_filename)}">
</head>
<body class="{printable_class}">
    {pages_html}
</body>
</html>
"""


def export_pdf(html_path: str, pdf_path: str):
    from playwright.sync_api import sync_playwright

    abs_html = Path(html_path).resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(abs_html, wait_until="networkidle")
        page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )
        browser.close()


def main():
    parser = argparse.ArgumentParser(description="Generar cartas de conjuros DnD.")
    parser.add_argument("input", help="Ruta al archivo JSON de entrada")
    parser.add_argument("-o", "--output", default="spells.html", help="Ruta del archivo HTML generado")
    parser.add_argument("-d", "--outdir", default="output", help="Directorio donde se guardarán los resultados")
    parser.add_argument("--css", default="styles.css", help="Ruta o nombre del archivo CSS externo")
    parser.add_argument("--pdf", nargs="?", const="", help="Exportar directamente a PDF")
    parser.add_argument("-p", "--printable", action="store_true", help="Modo sin fondo para imprimir")

    args = parser.parse_args()

    outdir_path = Path(args.outdir).resolve()
    output_path = (outdir_path / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(args.input, "r", encoding="utf-8") as f:
        spells = json.load(f)

    # Automatically split spells whose text exceeds the card dimensions
    paginated_spells = split_overflowing_spells(spells, css_filename=args.css)

    # Calculate relative path to CSS so the HTML link works inside the output folder
    css_path = Path(args.css).resolve()
    try:
        rel_css_path = str(css_path.relative_to(output_path.parent, walk_up=True)).replace("\\", "/")
    except ValueError:
        rel_css_path = str(css_path)

    html_content = generate_html(paginated_spells, css_filename=rel_css_path, printable=args.printable)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML generado -> {output_path} (usando {rel_css_path})")

    if args.pdf is not None:
        if args.pdf:
            pdf_path = (outdir_path / args.pdf).resolve()
        else:
            pdf_path = output_path.with_suffix(".pdf")
        
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Renderizando PDF -> {pdf_path}...")
        export_pdf(output_path, pdf_path)
        print("¡Completado!")


if __name__ == "__main__":
    main()