"""Deterministic critical-value gate (F-001 / F-022; mission principle 4).

A claim passes only if every critical value in it is present, by EXACT match, in the text of the
sources it cites. No embeddings and no LLM, so it works on the FULL chunk text regardless of the
embedder's 128-wordpiece window.

Critical values extracted (the same extraction runs on claim and sources):
  - number + unit pairs      "10 minutes" -> "10 min",  "३० mA" -> "30 mA",  "100 मिलीसेकंड" -> "100 ms"
  - error codes              "E-101", "E101", "E 101", "ई-१०१" -> "E101"  (E-0140 != E-014, E-O14 != E-014)
  - model designators        "AC-7", "DC-60", "HomeLine"

Rules: Devanagari digits equal Western digits. Units are normalised (min = minutes = मिनट) but
magnitude is part of the unit (mA != A, ms != s, kW != kWh, kV != V, degC != degF). A pair must match
as a pair: "50 minutes" is NOT supported by a source that only has "10 minutes" and "50 V". There is
no unit conversion: "600 s" is not supported by "10 minutes" (stricter than needed; the owner has not
yet approved a conversion rule).

Known limits (see docs/FAILURES.md): a number followed by a unit this module does not know is NOT
extracted, so it is not checked (fail-open). The Hindi unit-word list is UNREVIEWED by a native speaker.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Latin symbols are matched case-sensitively (mA is not MA).
_SYMBOLS = {
    "kWh": "kWh", "kW": "kW", "kV": "kV", "mA": "mA", "ms": "ms", "Nm": "Nm", "N·m": "Nm", "N-m": "Nm", "N.m": "Nm",
    "°C": "degC", "°F": "degF", "kOhm": "kohm", "kohm": "kohm", "Ohm": "ohm", "ohm": "ohm",
    "Hz": "Hz", "V": "V", "A": "A", "W": "W", "s": "s", "h": "h",
    "kVA": "kVA", "VA": "VA", "MVA": "MVA",
    "m": "m", "cm": "cm", "mm": "mm", "km": "km", "in": "in", "ft": "ft",
    "kg": "kg", "g": "g", "lb": "lb", "lbs": "lb",
    "ft-lb": "ft-lb", "ft-lbs": "ft-lb", "ft·lb": "ft-lb",
    "psi": "psi", "PSI": "psi", "bar": "bar",
    "%": "%",
}
# Latin words, case-insensitive.
_WORDS = {
    "minutes": "min", "minute": "min", "mins": "min", "min": "min",
    "seconds": "s", "second": "s", "secs": "s", "sec": "s",
    "milliseconds": "ms", "millisecond": "ms",
    "milliamperes": "mA", "milliampere": "mA", "milliamps": "mA", "milliamp": "mA",
    "amperes": "A", "ampere": "A", "amps": "A", "amp": "A",
    "kilovolts": "kV", "kilovolt": "kV", "volts": "V", "volt": "V",
    "kilowatts": "kW", "kilowatt": "kW", "ohms": "ohm",
    "hours": "h", "hour": "h",
    "degrees celsius": "degC", "degree celsius": "degC", "degc": "degC",
    "degrees fahrenheit": "degF", "degree fahrenheit": "degF", "degf": "degF",
    "inches": "in", "inch": "in", "meters": "m", "meter": "m", "metres": "m", "metre": "m",
    "millimeters": "mm", "millimeter": "mm", "millimetres": "mm", "millimetre": "mm",
    "centimeters": "cm", "centimeter": "cm", "centimetres": "cm", "centimetre": "cm",
    "kilometers": "km", "kilometer": "km", "kilometres": "km", "kilometre": "km",
    "feet": "ft", "foot": "ft",
    "kilograms": "kg", "kilogram": "kg", "kgs": "kg",
    "grams": "g", "gram": "g",
    "pounds": "lb", "pound": "lb",
    "newton-meters": "Nm", "newton-meter": "Nm", "newton meters": "Nm", "newton meter": "Nm",
    "newton-metres": "Nm", "newton-metre": "Nm", "newton metres": "Nm", "newton metre": "Nm",
    "foot-pounds": "ft-lb", "foot-pound": "ft-lb", "foot pounds": "ft-lb", "foot pound": "ft-lb",
    "percent": "%",
}
# Hindi unit words: UNREVIEWED by a native speaker.
_HINDI = {
    "मिनट": "min", "मिनटों": "min", "मिनिट": "min",
    "सेकंड": "s", "सेकंडों": "s", "सेकण्ड": "s", "सेकेंड": "s", "सैकंड": "s",
    "मिलीसेकंड": "ms", "मिलीसेकण्ड": "ms", "मिलीसेकेंड": "ms",
    "घंटा": "h", "घंटे": "h", "घंटों": "h", "घण्टा": "h", "घण्टे": "h",
    "मिलीएम्पियर": "mA", "मिलीऐम्पियर": "mA", "एम्पियर": "A", "ऐम्पियर": "A", "एम्प": "A",
    "किलोवोल्ट": "kV", "वोल्ट": "V", "किलोवाट": "kW", "वाट": "W",
    "किलोओम": "kohm", "ओम": "ohm",
    "मीटर": "m", "मी": "m",
    "मिलीमीटर": "mm", "मिमी": "mm",
    "सेंटीमीटर": "cm", "सेमी": "cm",
    "किलोमीटर": "km", "किमी": "km",
    "इंच": "in", "फीट": "ft", "फुट": "ft",
    "किलोग्राम": "kg", "किलो": "kg", "किग्रा": "kg",
    "ग्राम": "g", "पाउंड": "lb",
    "न्यूटन-मीटर": "Nm", "न्यूटन मीटर": "Nm", "न्यूटन-मी": "Nm",
    "डिग्री सेल्सियस": "degC",
    "प्रतिशत": "%",
}


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


_UNIT_CANON = {
    **{_nfc(k): v for k, v in _SYMBOLS.items()},
    **{_nfc(k).lower(): v for k, v in _WORDS.items()},
    **{_nfc(k): v for k, v in _HINDI.items()},
}


def _alt(keys) -> str:
    return "|".join(re.escape(_nfc(k)) for k in sorted(keys, key=len, reverse=True))


_UNIT = (f"(?:(?i:{_alt(_WORDS)})|{_alt(_HINDI)}|{_alt(_SYMBOLS)})"
         r"(?![A-Za-z0-9ऀ-ॿ])")
_NUM = r"(?<![\w.])(?P<n>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
_PAIR = re.compile(_NUM + r"\s*[-‐-–]?\s*(?P<u>" + _UNIT + ")")
# "200 to 500 V": the first number shares the unit of the second.
_RANGE = re.compile(_NUM + r"\s*(?:to|-|–|से)\s*(?P<n2>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*[-‐-–]?\s*(?P<u>"
                    + _UNIT + ")")
# E-101, E101, E 101 (3-4 chars when separated by a space), E-14H, E-O14 (letter O), E-l14 (lowercase L)
_CODE = re.compile(r"(?<![A-Za-z0-9])[Eeई](?:-[0-9OIl]{2,4}|\s?[0-9OIl]{3,4})[A-Z]?(?![A-Za-z0-9])")
_MODEL = re.compile(r"(?<![A-Za-z])(?:AC|DC)-\d{1,3}(?!\d)|HomeLine")
_OCPP = re.compile(r"\b[A-Z][a-zA-Z0-9]+(?:Request|Response)\b")
_CITATION = re.compile(r"\[\d+\]")


@dataclass
class GateResult:
    passed: bool
    missing: list[str] = field(default_factory=list)       # claim values not found in any source
    claim_values: list[str] = field(default_factory=list)  # everything the gate checked


def _number(text: str) -> str | None:
    try:
        d = Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None
    return format(d.normalize(), "f")


def _unit(surface: str) -> str:
    s = _nfc(surface)
    return _UNIT_CANON.get(s) or _UNIT_CANON[s.lower()]


def extract_critical_values(text: str) -> set[str]:
    text = _nfc(text).translate(_DEVANAGARI_DIGITS)
    text = _CITATION.sub(" ", text)
    values: set[str] = set()
    for m in _PAIR.finditer(text):
        n = _number(m.group("n"))
        if n is not None:
            values.add(f"{n} {_unit(m.group('u'))}")
    for m in _RANGE.finditer(text):
        n = _number(m.group("n"))
        if n is not None:
            values.add(f"{n} {_unit(m.group('u'))}")
        n2 = _number(m.group("n2"))
        if n2 is not None:
            values.add(f"{n2} {_unit(m.group('u'))}")
    for m in _CODE.finditer(text):
        code = re.sub(r"[-\s]", "", m.group(0))
        values.add("E" + code[1:])
    for m in _MODEL.finditer(text):
        values.add(m.group(0))
    for m in _OCPP.finditer(text):
        values.add(m.group(0))
    return values


def gate_claim(claim: str, sources: list[str]) -> GateResult:
    """Pass only if every critical value in `claim` appears (exactly) in at least one of `sources`.

    Sources are extracted one by one and unioned, so a number at the end of one chunk is never
    joined with a unit at the start of the next.
    """
    claim_values = extract_critical_values(claim)
    source_values: set[str] = set()
    for s in sources:
        source_values |= extract_critical_values(s)
    missing = sorted(claim_values - source_values)
    return GateResult(passed=not missing, missing=missing, claim_values=sorted(claim_values))
