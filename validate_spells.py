import json
import sys
from jsonschema import Draft7Validator

# Schema based on Brian Wendt's Spell.schema.json definition
SPELL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "Spell.schema.json",
    "type": "object",
    "required": [
        "name",
        "description",
        "level",
        "casting_time",
        "range_area",
        "components",
        "duration",
    ],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "higher_level": {"type": "string"},
        "level": {
            "type": "string",
            "enum": ["Cantrip", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
        },
        "casting_time": {"type": "string"},
        "range_area": {"type": "string"},
        "components": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["V", "S", "M", "F", "DF", "XP"],
            },
        },
        "material": {"type": "string"},
        "ritual": {"type": "boolean", "default": False},
        "concentration": {"type": "boolean", "default": False},
        "duration": {"type": "string"},
        "school": {"type": "string"},
        "attack_save": {"type": "string"},
        "damage_effect": {"type": "string"},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "source": {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {
                    "type": "string"
                },
                "note": {
                    "type": "string"
                },
                "href": {
                    "type": "string",
                    "format": "uri"
                }
            },
            "additionalProperties": True
        },
        "icon": {
            "type": "string",
            "description": "Optional image URL or relative path for the card header icon."
        }
    },
    "additionalProperties": True,
}


def validate_spell_file(json_filepath: str) -> bool:
    with open(json_filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"Error: The root of '{json_filepath}' must be a JSON array of spells.")
        return False

    validator = Draft7Validator(SPELL_SCHEMA)
    all_valid = True

    print(f"Validating {len(data)} spells from '{json_filepath}'...\n")

    for idx, spell in enumerate(data):
        spell_name = spell.get("name", f"Spell at index {idx}")
        errors = list(validator.iter_errors(spell))

        if errors:
            all_valid = False
            print(f"❌ '{spell_name}' (index {idx}):")
            for err in errors:
                field_path = " -> ".join([str(p) for p in err.path]) or "root"
                print(f"   • [{field_path}] {err.message}")
        else:
            print(f"✓ '{spell_name}' is valid.")

    if all_valid:
        print(f"\nAll {len(data)} spells passed schema validation successfully.")
    else:
        print("\nSome spells failed validation. See above for details.")

    return all_valid


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "spells.json"
    success = validate_spell_file(filepath)
    sys.exit(0 if success else 1)