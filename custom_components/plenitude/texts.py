"""Texts that Home Assistant's translation files cannot carry: names of statistics, entry title, device model.

Statistic names are stored in the recorder when the statistics are imported, so they follow the language of the
Home Assistant server (Settings > System > General), not the language of each user. Everything the users see in
the interface (configuration, options, entities, errors) is in ``translations/``; the cards have their own texts.

Like ``api`` and ``bands``, this module does not import Home Assistant.
"""

from __future__ import annotations

ITALIAN = "it"
ENGLISH = "en"

TEXTS = {
    ITALIAN: {
        "title": "Plenitude luce",
        "model": "Fornitura luce",
        "energy": "consumo",
        "band": "consumo {band}",
        "cost": "costo",
        "estimate": "{name} (stima)",
    },
    ENGLISH: {
        "title": "Plenitude electricity",
        "model": "Electricity supply",
        "energy": "consumption",
        "band": "consumption {band}",
        "cost": "cost",
        "estimate": "{name} (estimate)",
    },
}

# Estimated consumption categories of the portal. The Italian names are the portal's own (2026-11-22); the
# portal sends them with the data and they replace these when they differ.
CATEGORY_NAMES = {
    ITALIAN: {
        "comfort_ambientale": "Comfort ambientale (HVAC)",
        "standby": "Standby",
        "lavare": "Lavare",
        "elettronica_luci": "Elettronica e luci",
        "refrigerare": "Refrigerare",
        "cucinare": "Cucinare",
        "ricarica_elettrica": "Ricarica elettrica",
        "altro": "Altro",
    },
    ENGLISH: {
        "comfort_ambientale": "Heating and cooling (HVAC)",
        "standby": "Standby",
        "lavare": "Washing",
        "elettronica_luci": "Electronics and lighting",
        "refrigerare": "Refrigeration",
        "cucinare": "Cooking",
        "ricarica_elettrica": "EV charging",
        "altro": "Other",
    },
}


def language(code: str | None) -> str:
    """Italian for ``it`` and its variants, English for everything else."""
    return ITALIAN if (code or "").lower().startswith(ITALIAN) else ENGLISH


def text(lang: str, key: str, **values: str) -> str:
    return TEXTS[language(lang)][key].format(**values)
