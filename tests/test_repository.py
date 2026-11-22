"""Consistency of the files around the code: translations, versions, manifest (no Home Assistant needed)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
INTEGRATION = ROOT / "custom_components" / "plenitude"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(tree: dict, prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def test_translations_have_the_same_keys_and_placeholders() -> None:
    strings = _load(INTEGRATION / "strings.json")
    english = _load(INTEGRATION / "translations" / "en.json")
    italian = _load(INTEGRATION / "translations" / "it.json")
    assert strings == english, "strings.json is the English source: keep translations/en.json identical"
    flat_en, flat_it = _flatten(english), _flatten(italian)
    assert flat_en.keys() == flat_it.keys()
    for key, text in flat_en.items():
        placeholders = set(re.findall(r"\{(\w+)\}", text))
        assert placeholders == set(re.findall(r"\{(\w+)\}", flat_it[key])), key


def test_errors_raised_in_the_code_are_translated() -> None:
    source = "".join(path.read_text(encoding="utf-8") for path in INTEGRATION.glob("*.py"))
    keys = set(re.findall(r'translation_domain=DOMAIN,\s*translation_key="(\w+)"', source))
    assert keys and keys <= set(_load(INTEGRATION / "strings.json")["exceptions"])


def test_card_texts_exist_in_both_languages() -> None:
    cards = (INTEGRATION / "frontend" / "plenitude-cards.js").read_text(encoding="utf-8")
    blocks = re.search(r"const STRINGS = \{\s*it: \{(.*?)\n  \},\s*en: \{(.*?)\n  \},\n\};", cards, re.DOTALL)
    assert blocks
    keys = [set(re.findall(r"^\s{4}(\w+):", block, re.MULTILINE)) for block in blocks.groups()]
    assert keys[0] == keys[1]


def _first(pattern: str, path: Path) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, (pattern, path)
    return match.group(1)


def test_versions_match() -> None:
    manifest = _load(INTEGRATION / "manifest.json")["version"]
    const = _first(r'^VERSION = "([^"]+)"', INTEGRATION / "const.py")
    cards = _first(r'^const CARD_VERSION = "([^"]+)";', INTEGRATION / "frontend" / "plenitude-cards.js")
    changelog = _first(r"^## \[(\d+\.\d+\.\d+)\]", ROOT / "CHANGELOG.md")
    assert manifest == const == cards == changelog


def test_manifest_keys_in_hassfest_order() -> None:
    keys = list(_load(INTEGRATION / "manifest.json"))
    assert keys[:2] == ["domain", "name"] and keys[2:] == sorted(keys[2:])


def test_hacs_minimum_version_matches_the_readme() -> None:
    minimum = _load(ROOT / "hacs.json")["homeassistant"]
    major_minor = ".".join(minimum.split(".")[:2])
    for readme in ("README.md", "README.it.md"):
        assert major_minor in (ROOT / readme).read_text(encoding="utf-8"), readme
