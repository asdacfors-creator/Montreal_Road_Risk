# Outcome Observation Policy

**Project:** Montreal Road Risk  
**Phase:** Phase 4 — Leakage-Safe Labels and Feature Engineering  
**Version:** 1.0  
**Date:** 2026-07-18  

---

## 1. Target Estimand

The primary project outcome is:

> **The probability that a Géobase road segment has at least one mechanized
> pothole-repair event recorded in the official published annual Ville de
> Montréal mechanized-repair resources during the future target window.**

This estimand explicitly excludes:

- Borough-operated manual repairs
- Private or contractor repairs not recorded in the annual resources
- Physical potholes that were repaired but not captured in the annual mechanized-repair data

The exclusion of non-mechanized and borough repairs is a **source-scope limitation**, not an unobserved outcome. It is documented, preserved, and carried forward as a modeling assumption.

---

## 2. Coverage Policy

### 2.1 Published-Resource Observation Universe (Primary)

| Rule | Detail |
|---|---|
| Coverage definition | Each finalized official annual resource constitutes the complete observation universe for all mechanized repairs recorded for that year |
| Absence interpretation | A date without an event means "no event recorded in the finalized annual resource" — it does **not** claim no physical repair occurred |
| Date inference | First/last event dates in each resource are **not** used as reporting-period boundaries |
| Source | Ten annual resources: 2016–2025 (some covering multi-year periods) |
| Eligibility rule | All 102 month-end anchors in 2016-12 through 2025-03 are eligible |
| 90-day eligible anchors | **102** |
| 180-day eligible anchors | **102** |

### 2.2 Strict Verified-Completeness (Sensitivity Only)

This policy requires explicit documentary evidence of a complete, verified reporting period with no known gaps.

| Result | Value |
|---|---|
| 90-day eligible anchors | **0** |
| 180-day eligible anchors | **0** |

No annual resource has an explicit, authoritative reporting-period start and end date with verified completeness certification. Therefore no anchor is eligible under this policy.

This is a sensitivity policy. The primary analysis uses the published-resource policy.

---

## 3. Coverage Evidence Table

Every coverage interval is documented by source file, not by parsed calendar year.

| source_year | source_file | coverage_start | coverage_end | coverage_status | finalized | evidence_source |
|---|---|---|---|---|---|---|
| 2016 | reparation-nids-de-poule-2016.csv | 2016-01-01 | 2016-12-31 | verified_observed | 1 | Annual resource (raw range ends 2016-12-24; calendar year boundary applied per §2.1) |
| 2017 | reparation-nids-de-poule-2017.csv | 2017-01-01 | 2017-12-31 | verified_observed | 1 | Annual resource |
| 2018 | reparation-nids-de-poule-2018.csv | 2018-01-01 | 2018-12-31 | verified_observed | 1 | Annual resource |
| 2019 | reparation-nids-de-poule-2019.csv | 2019-01-01 | 2019-12-31 | verified_observed | 1 | Annual resource; no-record interval Jun–Oct documented as L3.1 |
| 2020 | (no source file) | — | — | documented_gap | — | No 2020 annual resource published; L3.2 |
| 2021 | reparation-nids-de-poule-2021.csv | 2021-01-01 | 2021-12-31 | verified_observed | 1 | Annual resource |
| 2022 | reparation-nids-de-poule-2022.csv | 2022-01-01 | 2022-12-31 | verified_observed | 1 | Annual resource |
| 2023 | reparation-nids-de-poule-2023.csv | 2023-01-01 | 2023-12-31 | verified_observed | 1 | Annual resource; 2022-12-20 event belongs to 2023 source (not used to extend 2022 coverage) |
| 2024 | reparation-nids-de-poule-2024.csv | 2024-01-01 | 2024-12-31 | verified_observed | 1 | Annual resource; Nov 2023 events belong to 2024 source |
| 2025 | reparation-nids-de-poule-2025.gpkg | 2025-01-01 | 2025-12-31 | verified_observed | 1 | Annual resource (still updating at acquisition) |

**Key provenance rules:**
- Out-of-year events are preserved in the repair ledger but do **not** extend source-file coverage to another year.
- 2022-12-20 event → 2023 source file → does not extend 2022 coverage.
- November 2023 events → 2024 source file → does not extend 2023 coverage.
- Four 2024-source year mismatches (events with source_year ≠ parsed year) → preserved as mismatches; timestamps used as-is.

---

## 4. Target Windows

| Target | Window | Policy | Null | Notes |
|---|---|---|---|---|
| `target_repair_90d` | `(as_of_date, as_of_date + 90 days]` | Published-resource | No | Primary target |
| `target_repair_180d` | `(as_of_date, as_of_date + 180 days]` | Published-resource | No | Sensitivity target |
| `target_repair_90d_strict` | `(as_of_date, as_of_date + 90 days]` | Strict completeness | Yes (all null) | Sensitivity — zero eligible anchors |
| `target_repair_180d_strict` | `(as_of_date, as_of_date + 180 days]` | Strict completeness | Yes (all null) | Sensitivity — zero eligible anchors |

> [!IMPORTANT]
> Target windows are half-open on the left: `as_of_date` itself is excluded. Events
> on `as_of_date` are historical, not target events.

---

## 5. Scope Limitations

| ID | Limitation |
|---|---|
| L2.1 | Borough-operated and manual repairs are excluded from all resources |
| L2.2 | The published-resource policy is a modeling assumption, not a verified-completeness claim |
| L3.1 | 2019 resource has no recorded events June–October (no-record interval) |
| L3.2 | No 2020 annual resource was published |
| L3.3 | 2025 resource was still updating at acquisition date |
| L3.4 | Source-year mismatches: 5 events have parsed year ≠ source file year; timestamps are used as-is |

---

## 6. References

- `data/metadata/pothole_resource_manifest.csv`
- `docs/data_audits/phase_4_preflight_report.md`
- `docs/decision_log.md` (D4.1 — Published-resource observation universe)
- `config/feature_engineering.json` → `coverage_policy`
