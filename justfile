[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

[unix]
set shell := ["sh", "-cu"]

# Default recipe: list available recipes
default:
    @just --list

# Set up virtual environment, sync dependencies with uv, and download Playwright Chromium
setup:
    uv sync
    uv run playwright install chromium

# Validate the spells JSON against the schema
validate input="data/spells.json":
    uv run python validate_spells.py {{input}}

# Generate HTML only
html input="data/spells.json" output="spells.html":
    uv run python dnd_spell_cards.py {{input}} -o {{output}}

# Generate HTML and export PDF (standard parchment style)
pdf input="data/spells.json" output="spells.html":
    uv run python dnd_spell_cards.py {{input}} -o {{output}} --pdf

# Generate printable ink-saver version (PDF + HTML)
printable input="data/spells.json" output="spells_printable.html":
    uv run python dnd_spell_cards.py {{input}} -o {{output}} -p --pdf

# Run full pipeline: validate schema, then generate both standard and printable PDFs
build input="data/spells.json":
    just validate {{input}}
    just pdf {{input}} spells.html
    just printable {{input}} spells_printable.html