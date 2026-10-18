#!/usr/bin/env python3
import argparse
import html
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from core.exporter import export_pdf
from core.paginator import (
    CHECK_OVERFLOW_JS,
    can_pack_into_k_cards,
    paginate_cards,
    render_preview_document,
)

STAT_LABELS: dict[str, str] = {
    "str": "FUE",
    "dex": "DES",
    "con": "CON",
    "int": "INT",
    "wis": "SAB",
    "cha": "CAR",
}


def format_mod(val: int) -> str:
    """Format ability score or save modifier with leading + or -."""
    return f"+{val}" if val >= 0 else str(val)


def calc_modifier(score: int) -> int:
    """Standard D&D modifier calculation."""
    return (score - 10) // 2


def format_speed(speed: dict) -> str:
    """Format speed dictionary into a compact string."""
    parts = []
    walk = speed.get("walk")
    if walk is not None:
        parts.append(f"{walk}m")
    for stype in ("fly", "swim", "climb", "burrow"):
        sval = speed.get(stype)
        if sval:
            label = {"fly": "vol", "swim": "nad", "climb": "trep", "burrow": "exc"}[stype]
            parts.append(f"{label} {sval}m")
    if speed.get("hover"):
        parts.append("(lev)")
    return ", ".join(parts)


def format_senses(senses: dict) -> str:
    """Format senses dictionary into a compact single-line string."""
    parts = []
    for sense, label in (
        ("darkvision", "visión en la oscuridad"),
        ("blindsight", "visión ciega"),
        ("tremorsense", "sentir vibraciones"),
        ("truesight", "visión verdadera"),
    ):
        dist = senses.get(sense)
        if dist:
            parts.append(f"{label} {dist} m")
    pp = senses.get("passive_perception")
    if pp is not None:
        parts.append(f"Percepción pasiva {pp}")
    return ", ".join(parts)


def format_saving_throws(saves: dict) -> str:
    """Return only saving throws that have non-zero or explicitly modified values."""
    parts = []
    for stat_key in ("str", "dex", "con", "int", "wis", "cha"):
        val = saves.get(stat_key, 0)
        if val != 0:
            parts.append(f"{STAT_LABELS[stat_key]} {format_mod(val)}")
    return ", ".join(parts)


def format_action_html(action: dict) -> str:
    """Render an individual action, attack, or trait to HTML."""
    name = html.escape(str(action.get("name", "")))
    attack = action.get("attack")
    effect = action.get("effect", "")

    if attack:
        raw_attack_type = str(attack.get("type", "Ataque con arma"))
        attack_type = html.escape(f"Tirada de ataque {raw_attack_type}")
        bonus = format_mod(attack.get("bonus", 0))
        reach = attack.get("reach")
        attack_range = attack.get("range")
        reach_str = f"alcance {reach}" if reach else f"alcance {attack_range}" if attack_range else ""
        hit = html.escape(str(attack.get("hit", "")))
        extra = html.escape(str(attack.get("extra", "")))

        atk_details = f"<em>{attack_type}:</em> {bonus}, {reach_str}. <em>Acierto:</em> {hit}."
        if extra:
            atk_details += f" {extra}"
        if effect:
            atk_details += f" {html.escape(effect)}"
        return f'<p class="entry-item"><span class="entry-name">{name}.</span> {atk_details}</p>'

    return f'<p class="entry-item"><span class="entry-name">{name}.</span> {html.escape(str(effect))}</p>'


def extract_creature_units(creature: dict) -> list[str]:
    """Break creature features into atomic HTML units with section headers."""
    units: list[str] = []

    traits = creature.get("traits", [])
    if traits:
        for t in traits:
            units.append(format_action_html(t))

    actions = creature.get("actions", [])
    if actions:
        units.append('<div class="section-title">Acciones</div>')
        for a in actions:
            units.append(format_action_html(a))

    bonus_actions = creature.get("bonus_actions", [])
    if bonus_actions:
        units.append('<div class="section-title">Acciones Adicionales</div>')
        for ba in bonus_actions:
            units.append(format_action_html(ba))

    reactions = creature.get("reactions", [])
    if reactions:
        units.append('<div class="section-title">Reacciones</div>')
        for r in reactions:
            units.append(format_action_html(r))

    return units


def build_creature_card_html(creature: dict, card_title: str | None = None, content_html: str | None = None) -> str:
    raw_title = card_title or creature.get("display_title") or creature.get("name", "")
    name = html.escape(str(raw_title))
    is_continuation = bool(re.search(r"\((?:[2-9]|\d{2,})/\d+\)$", name))

    cr_obj = creature.get("challenge_rating", {})
    cr_val = html.escape(str(cr_obj.get("cr", "")))

    if is_continuation:
        header_html = f"""
        <header class="creature-header header-continuation">
            <h1 class="creature-title">{name}</h1>
            <div class="cr-badge">
                <span class="cr-label">VD</span>
                <span class="cr-value">{cr_val}</span>
            </div>
        </header>
        """
        top_stats_html = ""
    else:
        # Full first-card header & stats block
        size = html.escape(str(creature.get("size", "")))
        ctype = html.escape(str(creature.get("type", "")))
        subtype = creature.get("subtype")
        type_str = f"{ctype} {size}" + (f" ({html.escape(subtype)})" if subtype else "")
        alignment = html.escape(str(creature.get("alignment", "")))
        subtitle = f"{type_str}, {alignment}"

        header_html = f"""
        <header class="creature-header">
            <div class="header-left">
                <h1 class="creature-title">{name}</h1>
                <div class="creature-subtitle">{subtitle}</div>
            </div>
            <div class="cr-badge">
                <span class="cr-label">VD</span>
                <span class="cr-value">{cr_val}</span>
            </div>
        </header>
        """

        ac = creature.get("armor_class", "")
        hp = html.escape(str(creature.get("hit_points", "")))
        speed = html.escape(format_speed(creature.get("speed", {})))
        initiative = html.escape(str(creature.get("initiative", "")))

        vitals_html = f"""
        <div class="vitals-strip">
            <div class="vital-box"><span class="vital-label">CA</span><span class="vital-value">{ac}</span></div>
            <div class="vital-box"><span class="vital-label">PG</span><span class="vital-value">{hp}</span></div>
            <div class="vital-box"><span class="vital-label">VEL</span><span class="vital-value">{speed}</span></div>
            <div class="vital-box"><span class="vital-label">INIC</span><span class="vital-value">{initiative}</span></div>
        </div>
        """

        scores = creature.get("ability_scores", {})
        ability_cols = []
        for stat in ("str", "dex", "con", "int", "wis", "cha"):
            score = scores.get(stat, 10)
            mod = format_mod(calc_modifier(score))
            ability_cols.append(
                f'<div class="ability-col">'
                f'<span class="ability-name">{STAT_LABELS[stat]}</span>'
                f'<span class="ability-mod">{mod}</span>'
                f'<span class="ability-score">{score}</span>'
                f"</div>"
            )
        ability_grid_html = f'<div class="ability-grid">{"".join(ability_cols)}</div>'

        attr_lines = []
        saves = format_saving_throws(creature.get("saving_throws", {}))
        if saves:
            attr_lines.append(
                f'<div class="attr-line"><span class="attr-label">Salvaciones:</span> {html.escape(saves)}</div>'
            )

        skills = creature.get("skills")
        if skills:
            attr_lines.append(
                f'<div class="attr-line"><span class="attr-label">Habilidades:</span> {html.escape(skills)}</div>'
            )

        senses = format_senses(creature.get("senses", {}))
        if senses:
            attr_lines.append(
                f'<div class="attr-line"><span class="attr-label">Sentidos:</span> {html.escape(senses)}</div>'
            )

        languages = creature.get("languages")
        if languages:
            attr_lines.append(
                f'<div class="attr-line"><span class="attr-label">Idiomas:</span> {html.escape(languages)}</div>'
            )

        gear = creature.get("gear", [])
        if gear:
            attr_lines.append(
                f'<div class="attr-line"><span class="attr-label">Equipo:</span> {html.escape(", ".join(gear))}</div>'
            )

        attributes_html = f'<div class="attributes-block">{"".join(attr_lines)}</div>' if attr_lines else ""
        top_stats_html = f"{vitals_html}{ability_grid_html}{attributes_html}"

    body_content = content_html if content_html is not None else "".join(extract_creature_units(creature))

    return f"""
    <div class="card">
        <div class="card-inner">
            {header_html}
            {top_stats_html}
            <div class="creature-body card-body">
                {body_content}
            </div>
        </div>
    </div>
    """


def make_creature_candidate(creature: dict, units: list[str], card_num: int, total_cards: int) -> dict:
    base_name = creature.get("name", "")
    title = f"{base_name} ({card_num}/{total_cards})" if total_cards > 1 else base_name
    candidate = dict(creature)
    candidate["display_title"] = title
    candidate["_rendered_content"] = "".join(units)
    return candidate


def render_creature_candidate_card(creature: dict) -> str:
    return build_creature_card_html(
        creature,
        card_title=creature.get("display_title"),
        content_html=creature.get("_rendered_content"),
    )


def split_overflowing_creatures(creatures: list[dict], css_filename: str) -> list[dict]:
    css_path = Path(css_filename).resolve()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(device_scale_factor=2)
        page = context.new_page()
        page.emulate_media(media="print")

        processed_cards: list[dict] = []

        for creature in creatures:
            test_html = render_preview_document(build_creature_card_html(creature), css_path)
            page.set_content(test_html, wait_until="load")

            # Fits cleanly on 1 card
            if not page.evaluate(CHECK_OVERFLOW_JS):
                processed_cards.append(creature)
                continue

            units = extract_creature_units(creature)
            packed_cards = None
            for target_k in range(2, 6):
                packed_cards = can_pack_into_k_cards(
                    creature,
                    units,
                    target_k,
                    page,
                    css_path,
                    make_creature_candidate,
                    render_creature_candidate_card,
                )
                if packed_cards is not None:
                    break

            if packed_cards:
                processed_cards.extend(packed_cards)
            else:
                processed_cards.append(creature)

        browser.close()

    return processed_cards


def generate_html(
    creatures: list[dict],
    css_filename: str = "styles/creature_card.css",
    printable: bool = False,
) -> str:
    pages = paginate_cards(
        creatures,
        lambda c: build_creature_card_html(
            c,
            card_title=c.get("display_title"),
            content_html=c.get("_rendered_content"),
        ),
    )
    pages_html = "\n".join(pages)
    printable_class = " printable" if printable else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Cartas de Criaturas</title>
<link rel="stylesheet" href="{html.escape(css_filename)}">
</head>
<body class="{printable_class}">
    {pages_html}
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Generar cartas de criaturas/monstruos DnD.")
    parser.add_argument(
        "input",
        nargs="?",
        default="data/creatures.json",
        help="Ruta al archivo JSON de entrada",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="creatures.html",
        help="Ruta del archivo HTML generado",
    )
    parser.add_argument(
        "-d",
        "--outdir",
        default="output",
        help="Directorio donde se guardarán los resultados",
    )
    parser.add_argument(
        "--css",
        default="styles/creature_card.css",
        help="Ruta o nombre del archivo CSS externo",
    )
    parser.add_argument("--pdf", nargs="?", const="", help="Exportar directamente a PDF")
    parser.add_argument(
        "-p",
        "--printable",
        action="store_true",
        help="Modo sin fondo para imprimir",
    )

    args = parser.parse_args()

    outdir_path = Path(args.outdir).resolve()
    output_path = (outdir_path / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(args.input, encoding="utf-8") as f:
        creatures = json.load(f)

    paginated_creatures = split_overflowing_creatures(creatures, css_filename=args.css)

    css_path = Path(args.css).resolve()
    try:
        rel_css_path = str(css_path.relative_to(output_path.parent, walk_up=True)).replace("\\", "/")
    except ValueError:
        rel_css_path = str(css_path)

    html_content = generate_html(paginated_creatures, css_filename=rel_css_path, printable=args.printable)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML generado -> {output_path} (usando {rel_css_path})")

    if args.pdf is not None:
        pdf_path = (outdir_path / args.pdf).resolve() if args.pdf else output_path.with_suffix(".pdf")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Renderizando PDF -> {pdf_path}...")
        export_pdf(output_path, pdf_path)
        print("¡Completado!")


if __name__ == "__main__":
    main()
