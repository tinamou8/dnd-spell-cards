"""Unified schema validator for D&D cards (spells & creatures)."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).resolve().parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
DATA_DIR = PROJECT_ROOT / "data"

TARGET_CONFIG: dict[str, dict[str, Any]] = {
    "spells": {
        "schema_file": SCHEMAS_DIR / "spell.schema.json",
        "default_data": DATA_DIR / "spells.json",
        "label_plural": "spells",
    },
    "creatures": {
        "schema_file": SCHEMAS_DIR / "creature.schema.json",
        "default_data": DATA_DIR / "creatures.json",
        "label_plural": "creatures",
    },
}


def load_json(path: Path) -> Any:
    """Load and parse JSON content from a file."""
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_dataset(data_path: Path, target_type: str) -> bool:
    """Validate a JSON list file against its corresponding schema."""
    config = TARGET_CONFIG[target_type]
    schema_path: Path = config["schema_file"]
    label_plural: str = config["label_plural"]

    try:
        schema = load_json(schema_path)
    except FileNotFoundError:
        print(f"❌ Error: Missing schema at '{schema_path}'.")
        return False
    except json.JSONDecodeError as exc:
        print(f"❌ Error: Malformed schema JSON in '{schema_path}': {exc}")
        return False

    try:
        data = load_json(data_path)
    except FileNotFoundError:
        print(f"❌ Error: Data file not found at '{data_path}'.")
        return False
    except json.JSONDecodeError as exc:
        print(f"❌ Error: Malformed JSON in '{data_path}': {exc}")
        return False

    if not isinstance(data, list):
        print(f"❌ Error: Root of '{data_path}' must be a JSON array of {label_plural}.")
        return False

    validator = Draft7Validator(schema)
    all_valid = True

    print(f"Validating {len(data)} {label_plural} from '{data_path.name}' using '{schema_path.name}'...\n")

    for idx, item in enumerate(data):
        item_name = item.get("name", f"Item at index {idx}")
        errors = sorted(validator.iter_errors(item), key=lambda e: e.path)

        if errors:
            all_valid = False
            print(f"❌ '{item_name}' (index {idx}):")
            for err in errors:
                field_path = " -> ".join([str(p) for p in err.path]) or "root"
                print(f"   • [{field_path}] {err.message}")
        else:
            print(f"✓ '{item_name}' is valid.")

    if all_valid:
        print(f"\nAll {len(data)} {label_plural} passed schema validation successfully.\n")
    else:
        print(f"\nSome {label_plural} failed validation. Review the errors above.\n")

    return all_valid


def resolve_target_type(filepath: Path, explicit_type: str | None) -> str:
    """Infer target schema type from CLI argument or file name."""
    if explicit_type:
        return explicit_type

    filename = filepath.name.lower()
    if "creature" in filename or "monster" in filename:
        return "creatures"
    if "spell" in filename:
        return "spells"

    return "spells"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate spell or creature JSON data files against Draft-07 schemas.")
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        help="Path to the JSON file to validate (defaults to data/spells.json or data/creatures.json).",
    )
    parser.add_argument(
        "-t",
        "--type",
        choices=["spells", "creatures"],
        help="Target schema type. Inferred automatically if omitted.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all datasets (both spells.json and creatures.json).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Mode 1: Validate all default datasets
    if args.all or (args.file is None and args.type is None):
        success = True
        for target_key in ("spells", "creatures"):
            default_path = TARGET_CONFIG[target_key]["default_data"]
            if default_path.exists():
                is_ok = validate_dataset(default_path, target_key)
                success = success and is_ok
            else:
                print(f"⚠️ Skipping '{target_key}': '{default_path}' does not exist yet.")
        return 0 if success else 1

    # Mode 2: Validate a specific file or a single explicit type
    target_type = args.type
    target_file = args.file

    if target_file is None and target_type:
        target_file = TARGET_CONFIG[target_type]["default_data"]

    if target_file is None:
        print("❌ Error: No file specified to validate.")
        return 1

    inferred_type = resolve_target_type(target_file, target_type)
    success = validate_dataset(target_file, inferred_type)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
