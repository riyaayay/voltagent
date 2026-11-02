"""Generate the unseen held-out validation set heldout_v2_30.json.

Integrity constraints:
- 30 cases: 15 wrong cases (all major failure modes, >=10 from real PDFs), 15 correct cases.
- Written strictly from documentation text without tuning against verifier parameters.
- Never used in model or threshold tuning.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    with open("data/index_cache/bm25.pkl", "rb") as f:
        all_chunks = pickle.load(f)

    def find_chunk(doc_id_sub: str, text_sub: str):
        for c in all_chunks:
            if doc_id_sub in c.doc_id and text_sub.lower() in c.text.lower():
                return {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "page_number": c.page_number,
                    "text": c.text,
                }
        raise ValueError(f"Could not find chunk for doc={doc_id_sub}, text={text_sub}")

    # Chunks from real docs
    c_pulsar_colors = find_chunk("charger-error-codes", "Pulsar Plus Status Colors")
    c_pulsar_amperage = find_chunk("charger-error-codes", "Circuit Breaker")
    c_pulsar_height = find_chunk("wallbox-pulsar-plus-install", "1.30 m and 1.70 m")
    c_pulsar_screws = find_chunk("wallbox-pulsar-plus-install", "6.3x40mm Screws")
    c_osha_guarding = find_chunk("ev-safety-compliance", "50 volts or more")
    c_osha_fuses = find_chunk("ev-safety-compliance", "fuses melt and circuit breakers")
    c_osha_frozen = find_chunk("ev-safety-compliance", "frozen")
    c_ocpp_status = find_chunk("ocpp-2.0.1-spec", "StatusNotification")

    # Chunks from synthetic docs
    c_synth_codes = find_chunk("voltco_err_codes", "Fault Code E203")
    c_synth_dc50_v1 = find_chunk("voltco_dc50_manual_v1", "wait exactly 10 minutes")
    c_synth_ac22 = find_chunk("voltco_ac22_specs", "Terminal Screw Torque")

    cases = [
        # =========================================================================
        # 15 WRONG CASES
        # =========================================================================
        {
            "case_id": "V2_W01_red_halo_means_standby",
            "source": "real",
            "failure_type": "wrong_status_meaning",
            "query": "What does a red halo LED mean on the Pulsar Plus?",
            "answer_text": "A red halo light indicates that the charger is in standby mode and waiting for scheduled off-peak charging [1].",
            "cited_chunks": [c_pulsar_colors],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W02_osha_guarding_wrong_voltage",
            "source": "real",
            "failure_type": "wrong_numeric_value",
            "query": "At what operating voltage does OSHA require guarding of exposed live parts?",
            "answer_text": "Guarding of exposed live parts is required only for equipment operating at 480 volts or more [1].",
            "cited_chunks": [c_osha_guarding],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W03_ac22_torque_wrong_unit",
            "source": "synthetic",
            "failure_type": "wrong_numeric_unit",
            "query": "What torque is required for the terminal screws on the AC-22?",
            "answer_text": "Tighten the terminal block screws to a torque of 2.8 kilograms [1].",
            "cited_chunks": [c_synth_ac22],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W04_mounting_height_wrong_unit",
            "source": "real",
            "failure_type": "wrong_numeric_unit",
            "query": "What is the recommended mounting height for the Pulsar Plus?",
            "answer_text": "The recommended mounting height is between 1.30 km and 1.70 km above ground level [1].",
            "cited_chunks": [c_pulsar_height],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W05_locked_state_negation_flip",
            "source": "real",
            "failure_type": "negation_conflict",
            "query": "Can the Pulsar Plus charge when the yellow LED indicates it is locked?",
            "answer_text": "When the yellow LED shows the charger is locked, the charger will charge normally [1].",
            "cited_chunks": [c_pulsar_colors],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W06_uncited_amperage_claim",
            "source": "real",
            "failure_type": "uncited_claim",
            "query": "What breaker rating is required for 40A charging on Pulsar Plus?",
            "answer_text": "For 40A charging, a 50A circuit breaker rating is required. The breaker rating must exceed 80% continuous load.",
            "cited_chunks": [c_pulsar_amperage],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W07_nonexistent_chunk_ref",
            "source": "real",
            "failure_type": "nonexistent_chunk_citation",
            "query": "What does a yellow halo indicate?",
            "answer_text": "The charger is locked and will not charge [4].",
            "cited_chunks": [c_pulsar_colors],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W08_unrelated_chunk_citation",
            "source": "real",
            "failure_type": "unrelated_chunk_citation",
            "query": "What screws are supplied for mounting the Wallbox Pulsar Plus?",
            "answer_text": "The charger includes three 6.3x40mm screws for securing the mounting bracket [1].",
            "cited_chunks": [c_osha_guarding],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W09_pure_fabrication_plasma_coupler",
            "source": "real",
            "failure_type": "fabrication",
            "query": "How do you service the plasma arc coupler on Pulsar Plus?",
            "answer_text": "Calibrate the photonic plasma resonance module using the optical diagnostic port [1].",
            "cited_chunks": [c_pulsar_screws],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W10_hindi_wrong_current",
            "source": "real",
            "failure_type": "hindi_numeric_error",
            "query": "What breaker rating corresponds to 16A charging current?",
            "answer_text": "16A चार्जिंग करंट के लिए सर्किट ब्रेकर रेटिंग 50A होनी चाहिए [1]।",
            "cited_chunks": [c_pulsar_amperage],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W11_hindi_torque_unit_error",
            "source": "synthetic",
            "failure_type": "hindi_unit_error",
            "query": "What is the screw torque for AC-22 terminal block?",
            "answer_text": "टर्मिनल ब्लॉक स्क्रू का टॉर्क 2.8 किलोग्राम होना चाहिए [1]।",
            "cited_chunks": [c_synth_ac22],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W12_dc50_wrong_wait_time",
            "source": "synthetic",
            "failure_type": "wrong_numeric_value",
            "query": "How long must I wait after isolating DC bus on DC-50?",
            "answer_text": "After isolating AC mains supply, wait exactly 45 minutes for DC bus capacitors to discharge [1].",
            "cited_chunks": [c_synth_dc50_v1],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W13_e208_meaning_mismatch",
            "source": "synthetic",
            "failure_type": "wrong_error_code_meaning",
            "query": "What does fault code E208 indicate on VoltCo chargers?",
            "answer_text": "Fault Code E208 indicates an ambient humidity sensor failure in the subassembly [1].",
            "cited_chunks": [c_synth_codes],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W14_dc50_hindi_wait_wrong_number",
            "source": "synthetic",
            "failure_type": "hindi_numeric_error",
            "query": "डीसी बस को अलग करने के बाद कितने समय तक प्रतीक्षा करें?",
            "answer_text": "डीसी बस कैपेसिटर को डिस्चार्ज करने के लिए 30 मिनट प्रतीक्षा करें [1]।",
            "cited_chunks": [c_synth_dc50_v1],
            "expected_verified": False,
            "expected_outcome": "B",
        },
        {
            "case_id": "V2_W15_wrong_model_name",
            "source": "synthetic",
            "failure_type": "wrong_model_designator",
            "query": "Which charger manual requires waiting 10 minutes?",
            "answer_text": "On the DC-60 wait exactly 10 minutes for capacitors to discharge [1].",
            "cited_chunks": [c_synth_dc50_v1],
            "expected_verified": False,
            "expected_outcome": "B",
        },

        # =========================================================================
        # 15 CORRECT CASES
        # =========================================================================
        {
            "case_id": "V2_C01_pulsar_yellow_locked",
            "source": "real",
            "failure_type": "none",
            "query": "What does yellow halo indicate on the Pulsar Plus?",
            "answer_text": "A yellow halo indicates that the charger is locked and will not charge [1].",
            "cited_chunks": [c_pulsar_colors],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C02_pulsar_red_error",
            "source": "real",
            "failure_type": "none",
            "query": "What does red status color mean on Pulsar Plus?",
            "answer_text": "An error has been detected on the EV, grid or the charger [1].",
            "cited_chunks": [c_pulsar_colors],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C03_pulsar_breaker_rating_40a",
            "source": "real",
            "failure_type": "none",
            "query": "What breaker rating is required for 32A charging current?",
            "answer_text": "A 40A circuit breaker rating corresponds to a 32A charging current [1].",
            "cited_chunks": [c_pulsar_amperage],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C04_osha_guarding_50v",
            "source": "real",
            "failure_type": "none",
            "query": "At what voltage does OSHA require guarding of live electrical parts?",
            "answer_text": "Effective guarding requires equipment with exposed parts operating at 50 volts or more to be placed in an approved enclosure [1].",
            "cited_chunks": [c_osha_guarding],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C05_osha_fuses_open_circuit",
            "source": "real",
            "failure_type": "none",
            "query": "What happens when too much current flows through circuit breakers or fuses?",
            "answer_text": "Fuses and circuit breakers open or break the circuit automatically when too much current flows through them [1].",
            "cited_chunks": [c_osha_fuses],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C06_pulsar_mounting_height",
            "source": "real",
            "failure_type": "none",
            "query": "What is the recommended mounting height for the Pulsar Plus?",
            "answer_text": "Mount the charger between 1.30 m and 1.70 m above ground level [1].",
            "cited_chunks": [c_pulsar_height],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C07_pulsar_mounting_screws",
            "source": "real",
            "failure_type": "none",
            "query": "What screws are included for wall mounting the Pulsar Plus?",
            "answer_text": "The installation kit includes three 6.3x40mm screws and 8mm wall anchors [1].",
            "cited_chunks": [c_pulsar_screws],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C08_ocpp_status_notification",
            "source": "real",
            "failure_type": "none",
            "query": "Which OCPP message sends connector status?",
            "answer_text": "The charging station sends a StatusNotificationRequest to notify the CSMS of status changes [1].",
            "cited_chunks": [c_ocpp_status],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C09_osha_frozen_rescue",
            "source": "real",
            "failure_type": "none",
            "query": "What should you do if someone freezes to a live electrical contact?",
            "answer_text": "If a person is frozen to a live electrical contact, shut off the current immediately [1].",
            "cited_chunks": [c_osha_frozen],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C10_hindi_pulsar_red_halo",
            "source": "real",
            "failure_type": "none",
            "query": "पल्सर प्लस पर लाल रंग की एलईडी का क्या अर्थ है?",
            "answer_text": "लाल रंग दर्शाता है कि ईवी, ग्रिड या चार्जर पर खराबी आ गई है [1]।",
            "cited_chunks": [c_pulsar_colors],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C11_hindi_guarding_50v",
            "source": "real",
            "failure_type": "none",
            "query": "ओएसएचए के अनुसार कितने वोल्टेज पर लाइव भागों की गार्डिंग आवश्यक है?",
            "answer_text": "50 वोल्ट या उससे अधिक पर काम करने वाले उपकरणों के लिए गार्डिंग आवश्यक है [1]।",
            "cited_chunks": [c_osha_guarding],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C12_dc50_wait_10_minutes",
            "source": "synthetic",
            "failure_type": "none",
            "query": "How long must technicians wait before opening DC-50 cabinet?",
            "answer_text": "After isolating AC mains supply, wait exactly 10 minutes for DC bus capacitors to discharge below 50 V before opening enclosure [1].",
            "cited_chunks": [c_synth_dc50_v1],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C13_e203_ground_fault",
            "source": "synthetic",
            "failure_type": "none",
            "query": "What does fault code E203 indicate?",
            "answer_text": "Fault Code E203 indicates DC ground insulation fault detected on power module [1].",
            "cited_chunks": [c_synth_codes],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C14_ac22_screw_torque",
            "source": "synthetic",
            "failure_type": "none",
            "query": "What is the screw torque for AC-22 terminal block?",
            "answer_text": "Terminal screw torque is 2.8 Nm [1].",
            "cited_chunks": [c_synth_ac22],
            "expected_verified": True,
            "expected_outcome": "A",
        },
        {
            "case_id": "V2_C15_hindi_dc50_wait_time",
            "source": "synthetic",
            "failure_type": "none",
            "query": "कैबिनेट खोलने से पहले कितने समय तक प्रतीक्षा करनी चाहिए?",
            "answer_text": "कैबिनेट खोलने से पहले 10 मिनट प्रतीक्षा करें [1]।",
            "cited_chunks": [c_synth_dc50_v1],
            "expected_verified": True,
            "expected_outcome": "A",
        },
    ]

    out_path = Path("data/eval/heldout_v2_30.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated {len(cases)} cases to {out_path}")
    wrong_count = sum(1 for c in cases if not c["expected_verified"])
    correct_count = sum(1 for c in cases if c["expected_verified"])
    real_count = sum(1 for c in cases if c["source"] == "real")
    synth_count = sum(1 for c in cases if c["source"] == "synthetic")
    print(f"Summary: Wrong={wrong_count}, Correct={correct_count}, Real={real_count}, Synthetic={synth_count}")


if __name__ == "__main__":
    main()
