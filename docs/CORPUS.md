# Real Corpus Inventory (Phase 1.0)

Date: 2026-11-01
Total Real Documents: 5
Total Pages: 711
Extractable Pages: 710 (99.86%)
Total Chunks: 1,634
Scan Threshold: < 80% extractable pages (None flagged as scans; all 5 documents passed with >= 99.1% text-bearing pages).

## Document Summary Table

| Filename | doc_id | Page Count | Extractable Pages | Skipped Pages | Text Ratio | Chunks | Status | Publisher / Source |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ocpp-2.0.1-spec.pdf` | `ocpp-2.0.1-spec` | 481 | 481 | 0 | 100.0% | 1,192 | Verified Valid | Open Charge Alliance (OCA) — [OCPP 2.0.1 Part 2 Specification Ed. 2](https://www.openchargealliance.org/protocols/ocpp-201/) |
| `ocpp-2.0.1-appendices.pdf` | `ocpp-2.0.1-appendices` | 39 | 39 | 0 | 100.0% | 98 | Verified Valid | Open Charge Alliance (OCA) — [OCPP 2.0.1 Part 2 Appendices v1.3](https://www.openchargealliance.org/protocols/ocpp-201/) |
| `charger-error-codes.pdf` | `charger-error-codes` | 8 | 8 | 0 | 100.0% | 12 | Verified Valid | Wallbox — [Pulsar Plus NA Quick Reference & Status Guide](https://support.wallbox.com/na/) |
| `wallbox-pulsar-plus-install.pdf` | `wallbox-pulsar-plus-install` | 112 | 111 | 1 | 99.1% | 244 | Verified Valid | Wallbox — [Pulsar Plus Installation Guide](https://support.wallbox.com/) |
| `ev-safety-compliance.pdf` | `ev-safety-compliance` | 71 | 71 | 0 | 100.0% | 88 | Verified Valid | OSHA / U.S. Dept of Labor — [OSHA 3075 Controlling Electrical Hazards](https://www.osha.gov/publications/osha3075) |

---

## Document Analysis and Quality Findings

1. **`ocpp-2.0.1-spec.pdf` (`ocpp-2.0.1-spec`)**:
   - 481 pages, 1,192 chunks.
   - Comprehensive protocol specification for OCPP 2.0.1 Edition 2. Contains message structures (`TransactionEventRequest`, `AuthorizeRequest`, `StatusNotificationRequest`, `BootNotificationRequest`), requirement IDs (e.g., `J02.FR.17`), error codes (`ChargingFailure`, `GroundFailure`, `OverCurrentFailure`), and timeouts.
   - Quality: High-resolution digital PDF, clean table extraction, monospace message names intact.

2. **`ocpp-2.0.1-appendices.pdf` (`ocpp-2.0.1-appendices`)**:
   - 39 pages, 98 chunks.
   - Standardized components (Controller, Display, Recloser, AirCoolingSystem, ISO15118), variable definitions (`Active`, `Tripped`, `Problem`, `FanSpeed`), units (W, Wh, dateTime).
   - Quality: Clean tabular formatting.

3. **`charger-error-codes.pdf` (`charger-error-codes`)**:
   - 8 pages, 12 chunks.
   - Halo LED indicators (Green, Light Blue, Dark Blue pulsing, Yellow, Red) and troubleshooting procedures for Wallbox Pulsar Plus.
   - Quality: Crisp text layer; table columns parse cleanly into readable lines.

4. **`wallbox-pulsar-plus-install.pdf` (`wallbox-pulsar-plus-install`)**:
   - 112 pages, 244 chunks.
   - Electrical specifications: 16A to 48A current ratings, 208/240V AC, NEMA enclosure ratings, wire gauge requirements (AWG 6 to 10), torque specs (e.g. 1.2 Nm, 2.5 Nm), ground fault protection limits (20 mA / 30 mA).
   - Quality: 111 of 112 pages contain extractable text; 1 page is a cover/blank spacer.

5. **`ev-safety-compliance.pdf` (`ev-safety-compliance`)**:
   - 71 pages, 88 chunks.
   - OSHA 3075 electrical safety regulations, lock-out/tag-out (LOTO) protocols (29 CFR 1910.147 / 1910.331-335), minimum approach distances, arc flash PPE, shock current thresholds (1 mA perception, 5 mA GFCI limit, 10-20 mA let-go threshold, 100 mA ventricular fibrillation).
   - Quality: 100% extractable.

---

## Collision Check

- All 5 document IDs (`ocpp-2.0.1-spec`, `ocpp-2.0.1-appendices`, `charger-error-codes`, `wallbox-pulsar-plus-install`, `ev-safety-compliance`) are unique and collide with nothing in `data/raw/` (where synthetic documents use the prefix `D01_` through `D20_`).

