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
validate-all:
    uv run python validate.py --all

validate-spells input="data/spells.json":
    uv run python validate.py {{input}} -t spells

validate-creatures input="data/creatures.json":
    uv run python validate.py {{input}} -t creatures

# Generate HTML only
html input="data/spells.json" output="spells.html":
    uv run python build_spells.py {{input}} -o {{output}}

# Generate HTML and export PDF (standard parchment style)
pdf input="data/spells.json" output="spells.html":
    uv run python build_spells.py {{input}} -o {{output}} --pdf

# Generate printable ink-saver version (PDF + HTML)
printable input="data/spells.json" output="spells_printable.html":
    uv run python build_spells.py {{input}} -o {{output}} -p --pdf

# Generate creature HTML
creatures-html input="data/creatures.json" output="creatures.html":
    uv run python build_creatures.py {{input}} -o {{output}}

# Generate creature PDF
creatures-pdf input="data/creatures.json" output="creatures.html":
    uv run python build_creatures.py {{input}} -o {{output}} --pdf

# Generate printable (ink-saver) creature PDF
creatures-printable input="data/creatures.json" output="creatures.html":
    uv run python build_creatures.py {{input}} -o {{output}} -p --pdf

# Run full pipeline: validate schema, then generate both standard and printable PDFs
build input="data/spells.json":
    just validate {{input}}
    just pdf {{input}} spells.html
    just printable {{input}} spells_printable.html

# Format all files (code + import sorting)
format:
    uv run ruff format .
    uv run ruff check --fix .

# Check code style and formatting without modifying files (great for CI)
lint:
    uv run ruff check .
    uv run ruff format --check .
