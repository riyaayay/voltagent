"""Deterministic critical-value gate (F-001 / F-022; mission principle 4).

A claim passes only if every critical value in it (number+unit pair, error code, model designator)
is present, by EXACT match, in the cited source text. No embeddings, no LLM.

Hindi note: the Hindi/Devanagari strings below are UNREVIEWED test data. They exercise the gate's
mechanics (Devanagari numerals, Hindi unit words, mixed scripts) and are NOT ground truth for any
golden label until the owner clears them.
"""
import pytest

from voltagent.agents.numeric_gate import gate_claim

pytestmark = pytest.mark.unit

PASS_CASES = [
    ("en-en", "Wait 10 minutes before opening the cabinet",
     ["After isolating the DC bus, wait 10 minutes before opening the power cabinet."]),
    ("unit-abbreviation", "Wait 10 min", ["wait 10 minutes"]),
    ("hindi-claim-english-chunk", "कैबिनेट खोलने से पहले 2 मिनट प्रतीक्षा करें",
     ["Switch off breaker Q1, wait 2 minutes, then measure PE continuity."]),
    ("devanagari-numeral-latin-unit", "लीकेज करंट ३० mA से अधिक होने पर चार्जर बंद हो जाता है",
     ["Leakage current above 30 mA."]),
    ("devanagari-numeral-hindi-unit", "१०० मिलीसेकंड के बाद बंद हो जाता है",
     ["Output current above 40 A for more than 100 ms."]),
    ("hindi-claim-hindi-chunk", "2 मिनट प्रतीक्षा करें", ["ब्रेकर Q1 बंद करें, 2 मिनट प्रतीक्षा करें"]),
    ("latin-claim-devanagari-chunk", "Leakage trip is 30 mA", ["लीकेज ट्रिप सीमा ३० mA है"]),
    ("english-claim-hindi-chunk", "Wait 2 minutes", ["2 मिनट प्रतीक्षा करें"]),
    ("decimal-hindi-unit", "PE निरंतरता 0.3 ओम से कम होनी चाहिए", ["PE continuity must be below 0.3 ohm."]),
    ("decimal-devanagari", "०.३ ओम से कम", ["below 0.3 ohm"]),
    ("code-without-hyphen", "Error E101 means ground failure", ["E-101 GroundFailure"]),
    ("code-spoken-with-space", "E 101 hai", ["E-101 GroundFailure"]),
    ("code-devanagari-letter", "त्रुटि ई-१०१", ["E-101 GroundFailure"]),
    ("model-present", "On the AC-7 the code is E-101", ["Voltara AC-7: E-101 GroundFailure"]),
    ("range-first-number-inherits-unit", "DC output starts at 200 V", ["DC output 200 to 500 V"]),
    ("no-critical-values", "Switch off the breaker and lock it", ["unrelated text"]),
    ("citation-markers-are-not-values", "Wait 10 minutes [1][2].", ["wait 10 minutes"]),
    ("two-values-both-present", "Trip at 30 mA after 100 ms", ["trip 30 mA, delay 100 ms"]),
    ("values-spread-over-cited-chunks", "Wait 10 minutes and check below 50 V",
     ["wait 10 minutes", "bus voltage below 50 V"]),
    ("kv-stated-in-source", "The output is up to 0.5 kV", ["up to 0.5 kV, which is 500 V"]),
    ("degrees-celsius-symbol", "Shutdown at 85 °C", ["shutdown temperature is 85 °C (185 °F)"]),
]

FAIL_CASES = [
    ("wrong-number", "Wait 5 minutes", ["wait 10 minutes"], ["5 min"]),
    ("wrong-unit-seconds-vs-minutes", "Wait 10 seconds", ["wait 10 minutes"], ["10 s"]),
    ("wrong-unit-hindi-word", "10 सेकंड प्रतीक्षा करें", ["wait 10 minutes"], ["10 s"]),
    ("wrong-number-devanagari", "५ मिनट प्रतीक्षा करें", ["wait 10 minutes"], ["5 min"]),
    ("mA-vs-A", "Trip at 30 A", ["Trip at 30 mA"], ["30 A"]),
    ("ms-vs-s", "A delay of 100 s", ["A delay of 100 ms"], ["100 s"]),
    ("kW-vs-kWh", "It delivers 60 kWh of power", ["It delivers 60 kW of power"], ["60 kWh"]),
    ("kV-vs-V", "Up to 500 kV", ["Up to 500 V"], ["500 kV"]),
    ("devanagari-numeral-A-vs-mA", "लीकेज ट्रिप ३० A", ["Leakage trip 30 mA"], ["30 A"]),
    ("number-exists-with-another-unit", "Wait 50 minutes", ["wait 10 minutes", "below 50 V"], ["50 min"]),
    ("one-of-two-values-wrong", "Trip at 30 mA after 100 s", ["trip 30 mA, delay 100 ms"], ["100 s"]),
    ("absent-from-chunks", "Torque is 15 Nm", ["no torque information here"], ["15 Nm"]),
    ("code-absent", "Code E-102 applies", ["E-101 GroundFailure"], ["E102"]),
    ("code-0140-is-not-014", "Error E-0140", ["E-014 relay stuck closed"], ["E0140"]),
    ("code-letter-O-is-not-zero", "Error E-O14", ["E-014 relay stuck closed"], ["EO14"]),
    ("code-devanagari-wrong", "त्रुटि ई-१०२", ["E-101 GroundFailure"], ["E102"]),
    ("model-absent", "On the DC-60 wait 10 minutes", ["AC-7: wait 10 minutes"], ["DC-60"]),
    ("decimal-differs", "Below 0.5 ohm", ["below 0.3 ohm"], ["0.5 ohm"]),
    ("celsius-is-not-fahrenheit", "Shutdown at 85 °F", ["shutdown at 85 °C (185 °F)"], ["85 degF"]),
    ("no-unit-conversion-yet", "Wait 600 seconds", ["wait 10 minutes"], ["600 s"]),
]


@pytest.mark.parametrize("name, claim, sources", PASS_CASES, ids=[c[0] for c in PASS_CASES])
def test_supported_claims_pass(name, claim, sources):
    result = gate_claim(claim, sources)
    assert result.passed is True and result.missing == []


@pytest.mark.parametrize("name, claim, sources, missing", FAIL_CASES, ids=[c[0] for c in FAIL_CASES])
def test_unsupported_critical_values_fail_and_are_reported(name, claim, sources, missing):
    result = gate_claim(claim, sources)
    assert result.passed is False
    assert sorted(result.missing) == sorted(missing)
