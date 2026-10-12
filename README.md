# D&D 5e Spell Card Generator

A CLI utility designed to transform structured D&D 5e spell data into print-ready, high-resolution PDF and HTML card sheets formatted for standard card sleeves.

## Features

- **Standard TCG/MTG Dimensions:** Cards render at exactly **63.5 mm × 88 mm** (2.5″ × 3.5″), fitting standard card sleeves and proxy setups.
- **A4 Print Layout:** Optimized 3×3 grid per A4 sheet with zero-margin print styling.
- **Brian Wendt Schema Compatibility:** Built and validated against the community-standard [`Spell.schema.json`](https://brianwendt.github.io/dnd5e_json_schema/Spell.schema.json.html) specification.
- **Vector Graphics:** Level hexagons and card accents are rendered as scalable SVGs for crisp text and line borders in vector PDFs.
- **Ink-Saver Mode:** Includes a dedicated `--printable` flag to strip parchment backgrounds and heavy fills for economical home printing.
- **Fast Automation with `uv` & `just`:** Automated environment management, dependency synchronization, and Playwright browser installation.

## Prerequisites

1. **Python 3.13+**
2. **[uv](https://docs.astral.sh/uv/)**: Fast Python package and environment manager.
3. **[just](https://github.com/casey/just)**: Command runner used to automate tasks.

## Installing `just` on Windows

You can install `just` using any of the following Windows package managers:

### Option 1: Via Windows Package Manager (winget - Recommended)
Open PowerShell or Windows Terminal and run:
```powershell
winget install Casey.Just
```

### Option 2: Via Scoop
```powershell
scoop install just
```

### Option 3: Via Chocolatey
```powershell
choco install just
```

### Option 4: Via Cargo (Rust)
```powershell
cargo install just
```

---

Verify the installation by running:
```powershell
just --version
```

## Installing `uv` on Windows

Use this command from the official documentation (you need to have the right [execution policy](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-7.4#powershell-execution-policies)):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Setup & Installation

*Note: A sample JSON with a few spells is provided in the `data/` folder so you can test the generator immediately. You can place your own full JSON datasets in this folder.*

Clone the repository and run the setup recipe to create the virtual environment, install dependencies, and download the Chromium binary for Playwright:

```bash
just setup
```

## Available Commands

All standard workflows are defined in the `justfile`:

| Command | Description |
| :--- | :--- |
| `just` | Lists all available recipes and descriptions. |
| `just setup` | Synchronizes dependencies via `uv` and downloads the Playwright Chromium binary. |
| `just validate [input]` | Validates spell JSON data against the schema (defaults to `spells.json`). |
| `just html [input] [output]` | Generates the HTML layout only without exporting to PDF. |
| `just pdf [input] [output]` | Generates `spells.html` and exports `spells.pdf` in standard parchment style. |
| `just printable [input] [output]` | Generates the ink-saver version (`spells_printable.html` and PDF) with clean outlines. |
| `just build [input]` | Runs validation and builds both standard and printable PDFs in one step. |

## Manual Execution (Without `just`)

If you prefer running commands directly through `uv`:

```bash
# Sync dependencies
uv sync

# Install Playwright browser
uv run playwright install chromium

# Generate cards (Default)
uv run python dnd_spells.py spells.json --pdf

# Generate cards (Ink-saver)
uv run python dnd_spells.py spells.json -p --pdf

# Validate spell dataset
uv run python validate_spells.py spells.json
```

## Project Structure

```text
├── dnd_spell_cards.py   # Core card generation script (HTML & Playwright PDF export)
├── validate_spells.py   # Schema validation utility
├── styles.css           # CSS layout, @page rules, and typography
├── data/                # Directory for JSON inputs (contains sample data)
├── output/              # Generated HTML and PDF files will be saved here
├── justfile             # Command definitions for just
├── pyproject.toml       # Python dependencies and project configuration
└── README.md            # Project documentation
```

## License and Legal

### Code

The code in this repository is licensed under the [MIT License](LICENSE).

### Sample Data

This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The SRD 5.2.1 is licensed under the Creative Commons Attribution 4.0 International License, available at https://creativecommons.org/licenses/by/4.0/legalcode.

This project is compatible with fifth edition (5E).
