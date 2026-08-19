# ECCC Weather Station Selection and Rationale

This document details the selection and role assignment of historical daily weather stations for the Montreal Road Pavement Deterioration Risk MVP.

---

## 1. Selected Stations and Metadata

### Primary Station: MCTAVISH

*   **Station ID**: `10761`
*   **Climate ID**: `7024745`
*   **WMO ID**: `71612`
*   **TC ID**: `WTA`
*   **Location**: Latitude `45.50° N`, Longitude `73.58° W`
*   **Elevation**: `72.8` metres
*   **Role**: Primary source for temperature measurements (`max_temp`, `min_temp`, `mean_temp`) and candidate freeze–thaw counts.
*   **Selected Period**: 2009–2025 inclusive.

### Secondary Station: MONTREAL/PIERRE ELLIOTT TRUDEAU INTL

*   **Station ID**: `30165`
*   **Climate ID**: `702S006`
*   **WMO ID**: `71183`
*   **TC ID**: `WTQ`
*   **Location**: Latitude `45.47° N`, Longitude `73.74° W`
*   **Elevation**: `32.1` metres
*   **Role**: Secondary comparison, backup precipitation source, and potential temperature fallback candidate.
*   **Selected Period**: 2009–2025 inclusive.

---

## 2. Selection Rationale

1.  **Central Geographic Location**:
    *   The McTavish station is located on the slope of Mount Royal near downtown Montreal. Its central location provides an excellent representativeness of urban temperature fluctuations on the island.
    *   Montréal–Trudeau International Airport lies in the western-central region of the island, serving as a robust secondary fallback representing the airport-suburban microclimate.

2.  **Temperature Completeness Profile**:
    *   During the audit period 2009–2025, the McTavish station showed the highest temperature data completeness among candidate stations, with only **104** mean temperature records missing out of 6,209 calendar days (98.32% completeness).
    *   Montréal–Trudeau has **776** missing mean temperature records over the same period (87.50% completeness), making it less suitable as the primary temperature source but viable as a secondary fallback.

3.  **Cross-Station Correlation**:
    *   Over the 6,209 overlapping dates, the mean temperature correlation between McTavish and Montréal–Trudeau is extremely high at **0.998**.
    *   The mean temperature difference between the two stations is **0.426°C** (McTavish being slightly warmer due to the urban heat island effect).

---

## 3. Strict Rules & Constraints

> [!IMPORTANT]
> **No Station Mixing in Phase 2**:
> 1. Do not automatically fill McTavish missing values from Trudeau during Phase 2.
> 2. Do not combine the two stations into a processed weather series during Phase 2.
> 3. Any fallback, interpolation, station averaging, or bias adjustment requires an explicit Phase 3 policy.
> 4. Do not acquire Montréal/St-Hubert or other stations.
