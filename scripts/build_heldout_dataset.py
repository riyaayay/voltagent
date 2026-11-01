"""Build a NEW held-out evaluation dataset (Task 2).

Integrity Constraints:
- 30 wrong cases (22 real PDFs, 8 synthetic; all 10 failure modes represented).
- 30 correct cases (22 real PDFs, 8 synthetic).
- Built purely from source texts and failure type specifications without reading verifier implementation details.
- Never used in tuning.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Bootstrap sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voltagent.ingestion.loaders import load_pdf


def get_chunk(path: str, page_num: int, doc_id: str) -> dict:
    pages = load_pdf(path)
    match = next((p for p in pages if p.page_number == page_num), None)
    if not match:
        raise ValueError(f"Could not find page {page_num} in {path}")
    return {
        "chunk_id": f"{doc_id}:{page_num}:0",
        "doc_id": doc_id,
        "page_number": page_num,
        "text": match.text.strip(),
    }


def build_heldout():
    # Cache chunks from real documents
    chk_cec_p5 = get_chunk("data/raw/real/charger-error-codes.pdf", 5, "charger-error-codes")
    chk_cec_p6 = get_chunk("data/raw/real/charger-error-codes.pdf", 6, "charger-error-codes")
    chk_cec_p7 = get_chunk("data/raw/real/charger-error-codes.pdf", 7, "charger-error-codes")
    chk_wpp_p9 = get_chunk("data/raw/real/wallbox-pulsar-plus-install.pdf", 9, "wallbox-pulsar-plus-install")
    chk_wpp_p10 = get_chunk("data/raw/real/wallbox-pulsar-plus-install.pdf", 10, "wallbox-pulsar-plus-install")
    chk_wpp_p11 = get_chunk("data/raw/real/wallbox-pulsar-plus-install.pdf", 11, "wallbox-pulsar-plus-install")
    chk_wpp_p13 = get_chunk("data/raw/real/wallbox-pulsar-plus-install.pdf", 13, "wallbox-pulsar-plus-install")
    chk_osha_p8 = get_chunk("data/raw/real/ev-safety-compliance.pdf", 8, "ev-safety-compliance")
    chk_osha_p12 = get_chunk("data/raw/real/ev-safety-compliance.pdf", 12, "ev-safety-compliance")
    chk_osha_p13 = get_chunk("data/raw/real/ev-safety-compliance.pdf", 13, "ev-safety-compliance")
    chk_osha_p20 = get_chunk("data/raw/real/ev-safety-compliance.pdf", 20, "ev-safety-compliance")
    chk_osha_p28 = get_chunk("data/raw/real/ev-safety-compliance.pdf", 28, "ev-safety-compliance")
    chk_ocpp_p34 = get_chunk("data/raw/real/ocpp-2.0.1-spec.pdf", 34, "ocpp-2.0.1-spec")
    chk_ocpp_p52 = get_chunk("data/raw/real/ocpp-2.0.1-spec.pdf", 52, "ocpp-2.0.1-spec")
    chk_ocpp_p128 = get_chunk("data/raw/real/ocpp-2.0.1-spec.pdf", 128, "ocpp-2.0.1-spec")
    chk_ocpp_p140 = get_chunk("data/raw/real/ocpp-2.0.1-spec.pdf", 140, "ocpp-2.0.1-spec")

    # Synthetic chunks
    chk_ac22 = get_chunk("data/raw/synthetic/voltco_ac22_specs.pdf", 1, "voltco_ac22_specs")
    chk_dc50_v1 = get_chunk("data/raw/synthetic/voltco_dc50_manual_v1.pdf", 1, "voltco_dc50_manual_v1")
    chk_dc50_v2 = get_chunk("data/raw/synthetic/voltco_dc50_manual_v2.pdf", 1, "voltco_dc50_manual_v2")
    chk_errs = get_chunk("data/raw/synthetic/voltco_err_codes.pdf", 1, "voltco_err_codes")

    wrong_cases = [
        # --- Type 1: wrong_error_code_meaning (3 cases: 2 real, 1 synth) ---
        {
            "case_id": "HW01_red_led_meaning",
            "source": "real",
            "failure_type": "wrong_error_code_meaning",
            "query": "What does a steady red halo light indicate on the Pulsar Plus?",
            "answer_text": "A red halo light indicates that the vehicle is successfully charging and battery level is above 80% [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW02_purple_led_meaning",
            "source": "real",
            "failure_type": "wrong_error_code_meaning",
            "query": "What does purple LED halo light mean on Pulsar Plus?",
            "answer_text": "A purple halo light indicates the charger has lost power and needs a fuse replacement [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW03_e208_code_meaning",
            "source": "synthetic",
            "failure_type": "wrong_error_code_meaning",
            "query": "What does fault code E208 indicate on VoltCo chargers?",
            "answer_text": "Fault Code E208 indicates an ambient humidity sensor failure in the subassembly [1].",
            "cited_chunks": [chk_errs],
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 2: swapped_numeric_value (3 cases: 2 real, 1 synth) ---
        {
            "case_id": "HW04_shock_men_letgo",
            "source": "real",
            "failure_type": "swapped_numeric_value",
            "query": "What is the freezing current or let-go range for men?",
            "answer_text": "The freezing current or let-go range for men is 45 to 90 milliamperes where the individual cannot let go [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW05_women_letgo_range",
            "source": "real",
            "failure_type": "swapped_numeric_value",
            "query": "What current causes painful shock and muscular control loss in women?",
            "answer_text": "In women, painful shock and loss of muscular control occurs between 80 to 120 milliamperes [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW06_dc50_v2_wait_swap",
            "source": "synthetic",
            "failure_type": "swapped_numeric_value",
            "query": "How long must a technician wait after isolation on VoltCo DC-50 Rev 2?",
            "answer_text": "Wait exactly 45 minutes after isolating the DC bus before opening the power cabinet [1].",
            "cited_chunks": [chk_dc50_v2],
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 3: wrong_unit (3 cases: 2 real, 1 synth) ---
        {
            "case_id": "HW07_drilling_depth_unit",
            "source": "real",
            "failure_type": "wrong_unit",
            "query": "What drill hole depth is specified for the Pulsar Plus wall plate?",
            "answer_text": "Drill three holes with a diameter of 8 mm and minimum depth of 65 yards [1].",
            "cited_chunks": [chk_wpp_p10],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW08_body_shock_unit",
            "source": "real",
            "failure_type": "wrong_unit",
            "query": "At what current level can an electric shock cause severe muscular contractions?",
            "answer_text": "Extreme pain and severe muscular contractions occur between 50 and 150 kilovolts [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW09_ac22_screw_torque_unit",
            "source": "synthetic",
            "failure_type": "wrong_unit",
            "query": "What torque is required for VoltCo AC-22 terminal screws?",
            "answer_text": "The terminal screw torque specification for VoltCo AC-22 is 2.8 kilograms [1].",
            "cited_chunks": [chk_ac22],
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 4: negation_flip (3 cases: 2 real, 1 synth) ---
        {
            "case_id": "HW10_neutral_ground_bond",
            "source": "real",
            "failure_type": "negation_flip",
            "query": "Can the neutral conductor be bonded to ground downstream of the service disconnect?",
            "answer_text": "The neutral conductor shall be bonded to ground at all subpanels downstream of the disconnect [1].",
            "cited_chunks": [chk_osha_p20],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW11_open_cabinet_energized",
            "source": "real",
            "failure_type": "negation_flip",
            "query": "Can technicians open the charger enclosure while energized?",
            "answer_text": "Technicians can open the main power enclosure while the primary feeder remains energized [1].",
            "cited_chunks": [chk_wpp_p9],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW12_fan_failure_run",
            "source": "synthetic",
            "failure_type": "negation_flip",
            "query": "Will the VoltCo DC-50 operate if a cooling fan fails?",
            "answer_text": "The charger will operate at maximum capacity even when the internal cooling fan has failed [1].",
            "cited_chunks": [chk_dc50_v1],
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 5: wrong_ocpp_field_message (3 cases: 3 real) ---
        {
            "case_id": "HW13_ocpp_heartbeat_message",
            "source": "real",
            "failure_type": "wrong_ocpp_field_message",
            "query": "Which message is periodically sent to inform the CSMS the station is alive?",
            "answer_text": "The Charging Station periodically sends a FirmwareStatusNotificationRequest message to prove it is alive [1].",
            "cited_chunks": [chk_ocpp_p52],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW14_ocpp_authorize_message",
            "source": "real",
            "failure_type": "wrong_ocpp_field_message",
            "query": "Which request message does a charging station use to authenticate an RFID badge?",
            "answer_text": "To request authorization for an idToken the Charging Station sends a MeterValuesRequest message [1].",
            "cited_chunks": [chk_ocpp_p34],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW15_ocpp_status_notification",
            "source": "real",
            "failure_type": "wrong_ocpp_field_message",
            "query": "Which message reports a connector state change to Available or Occupied?",
            "answer_text": "A connector state change is communicated to the CSMS using the SetChargingProfileRequest message [1].",
            "cited_chunks": [chk_ocpp_p140],
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 6: citation_pointing_to_real_but_wrong_chunk (3 cases: 2 real, 1 synth) ---
        {
            "case_id": "HW16_citation_wrong_pdf",
            "source": "real",
            "failure_type": "citation_pointing_to_real_but_wrong_chunk",
            "query": "What is the recommended mounting height for Pulsar Plus?",
            "answer_text": "We recommend mounting the charging station at a height of 1.40 m above ground level [1].",
            "cited_chunks": [chk_osha_p8],  # cites OSHA title 29 standards chunk instead of wallbox install chunk
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW17_citation_wrong_page",
            "source": "real",
            "failure_type": "citation_pointing_to_real_but_wrong_chunk",
            "query": "What physiological effect does a 1 milliampere shock current have?",
            "answer_text": "A 1 milliampere current causes a faint tingling sensation in the body [1].",
            "cited_chunks": [chk_cec_p6],  # cites charger app troubleshooting instead of OSHA effects table
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW18_citation_wrong_spec",
            "source": "synthetic",
            "failure_type": "citation_pointing_to_real_but_wrong_chunk",
            "query": "What torque is required for VoltCo AC-22 terminal screws?",
            "answer_text": "The terminal screw torque specification for VoltCo AC-22 is 2.8 Nm [1].",
            "cited_chunks": [chk_dc50_v1],  # cites DC-50 manual instead of AC-22 specs
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 7: citation_to_nonexistent_chunk (3 cases: 2 real, 1 synth) ---
        {
            "case_id": "HW19_nonexistent_chunk_pulsar",
            "source": "real",
            "failure_type": "citation_to_nonexistent_chunk",
            "query": "What does green halo light mean on Pulsar Plus?",
            "answer_text": "Green halo light indicates charger is ready and no EV is connected [88].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW20_nonexistent_chunk_seqno",
            "source": "real",
            "failure_type": "citation_to_nonexistent_chunk",
            "query": "What is seqNo set to at transaction start?",
            "answer_text": "The seqNo field is initialized to 0 at transaction start [404].",
            "cited_chunks": [chk_ocpp_p128],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW21_nonexistent_chunk_ac22",
            "source": "synthetic",
            "failure_type": "citation_to_nonexistent_chunk",
            "query": "What is the nominal AC voltage for VoltCo AC-22?",
            "answer_text": "The nominal AC voltage for VoltCo AC-22 is 400 V AC [12].",
            "cited_chunks": [chk_ac22],
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 8: uncited_claim (3 cases: 2 real, 1 synth) ---
        {
            "case_id": "HW22_uncited_halo_yellow",
            "source": "real",
            "failure_type": "uncited_claim",
            "query": "What does a yellow halo mean on the Pulsar Plus?",
            "answer_text": "A steady yellow halo light indicates that the charger is locked and will not charge.",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW23_uncited_cat_meter",
            "source": "real",
            "failure_type": "uncited_claim",
            "query": "What meter category rating is required for electrical testing?",
            "answer_text": "Technicians must always verify zero voltage using a CAT III rated multimeter.",
            "cited_chunks": [chk_osha_p28],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW24_uncited_dc50_v1",
            "source": "synthetic",
            "failure_type": "uncited_claim",
            "query": "What is the maximum DC current for VoltCo DC-50 Rev 1?",
            "answer_text": "Maximum continuous DC output current on the Rev 1 unit is 125 A.",
            "cited_chunks": [chk_dc50_v1],
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 9: fluent_fabrication_no_basis_in_corpus (3 cases: 2 real, 1 synth) ---
        {
            "case_id": "HW25_fabrication_plasma_igniter",
            "source": "real",
            "failure_type": "fluent_fabrication_no_basis_in_corpus",
            "query": "How do you align the laser plasma igniter on the Pulsar Plus?",
            "answer_text": "Rotate the optical collimator dial on the laser plasma igniter until the beam aligns with receiver photodiode D-4 [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW26_fabrication_quantum_resistor",
            "source": "real",
            "failure_type": "fluent_fabrication_no_basis_in_corpus",
            "query": "What resistance is expected across the quantum entanglement shunt?",
            "answer_text": "The superconducting quantum entanglement shunt should measure exactly 0.0001 micro-ohms at absolute zero [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW27_fabrication_fusion_cell",
            "source": "synthetic",
            "failure_type": "fluent_fabrication_no_basis_in_corpus",
            "query": "How is tritium flushed from the VoltCo DC-50 fuel cell?",
            "answer_text": "Open tritium bypass petcock valve V-12 and flush with deuterated heavy water for 25 minutes [1].",
            "cited_chunks": [chk_dc50_v2],
            "expected_verified": False,
            "expected_outcome": "B1"
        },

        # --- Type 10: hindi_wrong_answer (3 cases: 3 real) ---
        {
            "case_id": "HW28_hindi_wrong_current_shock",
            "source": "real",
            "failure_type": "hindi_wrong_answer",
            "query": "5 मिलीएम्पियर करंट से शरीर पर क्या असर होता है?",
            "answer_text": "5 मिलीएम्पियर करंट लगने पर तुरंत कार्डियक अरेस्ट और गंभीर रूप से जान जाने का खतरा होता है [1]।",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW29_hindi_wrong_led_halo",
            "source": "real",
            "failure_type": "hindi_wrong_answer",
            "query": "पल्सर प्लस पर हरी बत्ती का क्या मतलब है?",
            "answer_text": "हरी लाइट का मतलब है कि चार्जर में शॉर्ट सर्किट की गंभीर खराबी पाई गई है [1]।",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
        {
            "case_id": "HW30_hindi_wrong_mounting_height",
            "source": "real",
            "failure_type": "hindi_wrong_answer",
            "query": "चार्जर को जमीन से कितनी ऊंचाई पर लगाना चाहिए?",
            "answer_text": "चार्जर को जमीन से कम से कम 15 मीटर की ऊंचाई पर स्थापित करने की सिफारिश की जाती है [1]।",
            "cited_chunks": [chk_wpp_p9],
            "expected_verified": False,
            "expected_outcome": "B1"
        },
    ]

    correct_cases = [
        # --- 30 Verified Correct Cases (22 real, 8 synthetic) ---
        {
            "case_id": "HC01_yellow_halo_locked",
            "source": "real",
            "query": "What does a yellow halo mean on Pulsar Plus?",
            "answer_text": "A yellow halo indicates the charger is locked and will not charge [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC02_green_halo_ready",
            "source": "real",
            "query": "What does a green halo light indicate on Pulsar Plus?",
            "answer_text": "A green halo light indicates no EV is connected to the charger and the charger is ready to use [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC03_light_blue_halo",
            "source": "real",
            "query": "What does light blue halo light signify on Pulsar Plus?",
            "answer_text": "Light blue halo indicates that an EV is connected to the charger and the charger is connecting [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC04_pulsing_dark_blue",
            "source": "real",
            "query": "What does pulsing dark blue LED mean on Pulsar Plus?",
            "answer_text": "A dark blue pulsing halo light indicates that vehicle charging is currently in progress [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC05_red_error_detected",
            "source": "real",
            "query": "What does a red halo light signify on Pulsar Plus?",
            "answer_text": "A red halo light indicates an error has been detected on the EV, the grid, or the charger [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC06_pulsing_purple_sync",
            "source": "real",
            "query": "What does pulsing purple halo light mean on Pulsar Plus?",
            "answer_text": "A pulsing purple halo light indicates the charger is synchronizing with the Wallbox app [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC07_white_light_tracking",
            "source": "real",
            "query": "What does spinning white halo mean on Pulsar Plus?",
            "answer_text": "A rotating white halo light indicates the charger is undergoing firmware update or initial setup [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC08_tingle_1ma",
            "source": "real",
            "query": "What bodily effect occurs at 1 milliampere current?",
            "answer_text": "An electric current of 1 milliampere produces a faint tingling sensation in the body [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC09_shock_5ma_slight",
            "source": "real",
            "query": "What sensation does a 5 milliampere current cause?",
            "answer_text": "At 5 milliamperes a slight shock is felt that is disturbing but the average individual can let go [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC10_men_letgo_range",
            "source": "real",
            "query": "What is the freezing current or let-go range for men?",
            "answer_text": "The freezing current or let-go range for men is 9 to 30 milliamperes where the individual cannot let go [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC11_women_letgo_range",
            "source": "real",
            "query": "What is the painful shock range for women?",
            "answer_text": "For women, painful shock and loss of muscular control occurs between 6 to 25 milliamperes [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC12_extreme_pain_current",
            "source": "real",
            "query": "What symptoms occur between 50 and 150 milliamperes current?",
            "answer_text": "Currents between 50 and 150 milliamperes cause extreme pain, respiratory arrest, and severe muscular contractions [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC13_cardiac_arrest_current",
            "source": "real",
            "query": "What happens at 10,000 milliamperes electric current?",
            "answer_text": "A current of 10,000 milliamperes causes cardiac arrest, severe burns, and probable death [1].",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC14_mounting_height_rec",
            "source": "real",
            "query": "What mounting height does Wallbox recommend for Pulsar Plus?",
            "answer_text": "Wallbox recommends mounting the charging station at a height of 1.40 m above ground level [1].",
            "cited_chunks": [chk_wpp_p9],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC15_mounting_height_bounds",
            "source": "real",
            "query": "What is the permitted mounting height range for Pulsar Plus?",
            "answer_text": "The mounting height y should be between 1.30 m and 1.70 m above ground level [1].",
            "cited_chunks": [chk_wpp_p9],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC16_drill_hole_diameter",
            "source": "real",
            "query": "What drill hole diameter is required for Pulsar Plus wall anchors?",
            "answer_text": "Install the wall anchors by drilling holes with a diameter of 8 mm [1].",
            "cited_chunks": [chk_wpp_p10],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC17_ocpp_seqno_zero",
            "source": "real",
            "query": "What should the seqNo be when a transaction starts in OCPP 2.0.1?",
            "answer_text": "When a transaction starts, the Charging Station SHOULD set the seqNo field for the TransactionEventRequest message to 0 [1].",
            "cited_chunks": [chk_ocpp_p128],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC18_ocpp_seqno_increment",
            "source": "real",
            "query": "How is the seqNo incremented after each TransactionEventRequest?",
            "answer_text": "After each TransactionEventRequest the Charging Station SHALL increase the seqNo by 1 [1].",
            "cited_chunks": [chk_ocpp_p128],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC19_osha_design_standards",
            "source": "real",
            "query": "Which federal regulations publish OSHA general electrical design standards?",
            "answer_text": "OSHA general industry electrical safety standards are published in Title 29 Code of Federal Regulations Part 1910.302 through 1910.308 [1].",
            "cited_chunks": [chk_osha_p8],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC20_circuit_continuous_load",
            "source": "real",
            "query": "What is the continuous circuit load percentage per NEC?",
            "answer_text": "Neither the charger nor vehicle draws more than 80% of the connected circuit maximum rating per National Electrical Code [1].",
            "cited_chunks": [chk_cec_p5],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC21_hindi_shock_1ma",
            "source": "real",
            "query": "1 मिलीएम्पियर करंट लगने पर शरीर पर क्या महसूस होता है?",
            "answer_text": "1 मिलीएम्पियर करंट लगने पर शरीर में केवल हल्की झनझनाहट (faint tingle) महसूस होती है [1]।",
            "cited_chunks": [chk_osha_p12],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC22_hindi_mounting_height",
            "source": "real",
            "query": "पल्सर प्लस को कितनी ऊंचाई पर लगाने की सिफारिश की गई है?",
            "answer_text": "चार्जिंग स्टेशन को जमीन से 1.40 m की ऊंचाई पर लगाने की सिफारिश की जाती है [1]।",
            "cited_chunks": [chk_wpp_p9],
            "expected_verified": True,
            "expected_outcome": "A"
        },

        # --- 8 Synthetic Correct Cases ---
        {
            "case_id": "HC23_ac22_terminal_torque",
            "source": "synthetic",
            "query": "What torque is specified for VoltCo AC-22 terminal screws?",
            "answer_text": "The terminal screw torque specification for VoltCo AC-22 is 2.8 Nm [1].",
            "cited_chunks": [chk_ac22],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC24_ac22_nominal_voltage",
            "source": "synthetic",
            "query": "What is the nominal AC voltage for VoltCo AC-22?",
            "answer_text": "The nominal AC voltage for the VoltCo AC-22 is 400 V AC [1].",
            "cited_chunks": [chk_ac22],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC25_dc50_v1_wait_time",
            "source": "synthetic",
            "query": "How long must a technician wait on VoltCo DC-50 Rev 1 before opening cabinet?",
            "answer_text": "Wait 10 minutes after isolating the DC bus before opening the power cabinet [1].",
            "cited_chunks": [chk_dc50_v1],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC26_dc50_v2_wait_time",
            "source": "synthetic",
            "query": "What is the capacitor discharge wait time for VoltCo DC-50 Rev 2?",
            "answer_text": "On VoltCo DC-50 Rev 2 wait 5 minutes after isolating the DC bus before opening the cabinet [1].",
            "cited_chunks": [chk_dc50_v2],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC27_dc50_v1_continuous_current",
            "source": "synthetic",
            "query": "What is max continuous current for VoltCo DC-50 Rev 1?",
            "answer_text": "Maximum continuous DC output current on VoltCo DC-50 Rev 1 is 125 A [1].",
            "cited_chunks": [chk_dc50_v1],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC28_e203_fault_meaning",
            "source": "synthetic",
            "query": "What does fault code E203 indicate on VoltCo chargers?",
            "answer_text": "Fault Code E203 indicates a DC ground insulation fault detected on the power module [1].",
            "cited_chunks": [chk_errs],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC29_e208_overcurrent",
            "source": "synthetic",
            "query": "What does fault code E208 indicate on VoltCo chargers?",
            "answer_text": "Fault Code E208 indicates output overcurrent detected on the DC charging bus [1].",
            "cited_chunks": [chk_errs],
            "expected_verified": True,
            "expected_outcome": "A"
        },
        {
            "case_id": "HC30_ac22_insulation_resistance",
            "source": "synthetic",
            "query": "What is minimum insulation resistance for VoltCo AC-22?",
            "answer_text": "Minimum insulation resistance specification for VoltCo AC-22 is 50 MOhm [1].",
            "cited_chunks": [chk_ac22],
            "expected_verified": True,
            "expected_outcome": "A"
        },
    ]

    all_cases = wrong_cases + correct_cases
    out_path = Path("data/eval/heldout_60.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_cases, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(all_cases)} held-out cases to {out_path}.")
    print(f"  Wrong cases:   {len(wrong_cases)} (Real: {sum(1 for c in wrong_cases if c['source'] == 'real')})")
    print(f"  Correct cases: {len(correct_cases)} (Real: {sum(1 for c in correct_cases if c['source'] == 'real')})")


if __name__ == "__main__":
    build_heldout()

