# Live Dashboard Demo Script — INSE 6311 Viva Defense
## Montreal Road Risk Assessment — Streamlit + Folium GIS Platform

**Target Duration:** 5 minutes  
**Dashboard URL:** `http://localhost:8501`  
**Pre-Demo Checklist:** Dashboard running, browser at 100% zoom, sidebar open, browser map fully loaded.

---

## Pre-Demo Setup (Do Before Entering the Room)

```bash
# Start dashboard 10 minutes early
cd D:\Montreal_Road_Risk
$env:PYTHONPATH=".;src"; .\.venv\Scripts\python.exe -m streamlit run app.py
```

- Open `http://localhost:8501` in Chrome or Edge
- Navigate to **Page 2 (Interactive Risk Map)** and let the map fully render
- Return to **App (Hero Landing)** before presenting
- Zoom browser to **100%** — no scrollbars visible

---

## MINUTE 0:00 – 0:45 | Hero Landing Page (`app.py`)

### Spoken Talking Points

> *"Welcome to the operational decision-support engine we built for Montréal road maintenance planning.
> This is the hero landing page — it shows our system at a glance: 47,983 canonical road segments,
> 527,813 evaluated observation-months, and our core performance metrics."*

### Actions

1. **[POINT]** to the hero banner: *"Title, subtitle, commit hash — everything is version-controlled."*
2. **[POINT]** to the 4 metric cards:
   - **AP:** `0.5057` — *"Average Precision on 11 future months the model never saw during training."*
   - **ROC-AUC:** `0.9210` — *"91% probability the model correctly ranks a high-risk segment above a low-risk one."*
   - **Top-10% Lift:** `6.58×` — *"The Top-10% list captures 65.8% of all actual repair sites — 6.58 times better than random."*
   - **Segments:** `47,983`
3. **[CLICK]** sidebar left: show the 5-page navigation structure.

---

## MINUTE 0:45 – 1:15 | Page 1 — Executive Overview

### Navigation

- **[CLICK]** sidebar → `1 Executive_Overview`

### Spoken Talking Points

> *"Page 1 gives planners a borough-level overview. They can see risk band distribution across the
> full Montréal network — how many segment-months fall into HIGH, MEDIUM, WATCH, and OTHER bands."*

### Actions

1. **[POINT]** to risk band summary table — highlight HIGH band segments.
2. **[POINT]** to the quarter/borough breakdown.
3. **[SAY]:** *"Every priority band is frozen post-Gate B2. HIGH means probability ≥ 0.177."*

---

## MINUTE 1:15 – 2:30 | Page 2 — Interactive Risk Map ⭐ CENTREPIECE

### Navigation

- **[CLICK]** sidebar → `2 Interactive_Risk_Map`

### Spoken Talking Points

> *"This is the centrepiece — an interactive Folium GIS choropleth map of all 47,983 Montréal road segments,
> coloured by predicted risk probability for the selected anchor month."*

### Actions

1. **[WAIT]** for map to fully render (~3 seconds after navigation).
2. **[POINT]** to colour gradient legend: *"Dark red = HIGH risk, blue = LOW risk."*
3. **[CLICK]** sidebar filter: Change **Priority Band** → `HIGH` only.
   - *"We can isolate the Top-HIGH band — approximately 26,000 segment-months per anchor."*
4. **[ZOOM IN]** on a densely red area (e.g., central borough).
5. **[CLICK]** on one red segment in the map.
   - *"Each segment is clickable — here we see the segment ID, predicted probability, and Top-3 SHAP drivers."*
6. **[POINT]** to popup: highlight `top_pos_feat_1` — likely a temperature or repair history feature.
7. **[RESET]** filter to `All` bands.

### Key Phrase

> *"This replaces a manual paper spreadsheet with a real-time GIS prioritization layer that planners can
> filter, zoom, and export — all without ever exposing outcome target labels."*

---

## MINUTE 2:30 – 3:15 | Page 3 — Segment Details

### Navigation

- **[CLICK]** sidebar → `3 Segment_Details`

### Spoken Talking Points

> *"Page 3 provides a per-segment drill-down. A planner selects any segment from the network and sees
> its full risk profile, historical repair timeline, and local SHAP explanation."*

### Actions

1. **[TYPE]** a high-risk segment ID (select one from the map popup earlier).
2. **[POINT]** to the segment risk time-series chart: *"We can see how probability changes across the 11 evaluated anchor months."*
3. **[POINT]** to SHAP waterfall chart: *"This is the local explanation — exactly which features pushed this specific segment's prediction up or down."*

---

## MINUTE 3:15 – 4:00 | Page 4 — Model Performance

### Navigation

- **[CLICK]** sidebar → `4 Model_Performance`

### Spoken Talking Points

> *"Page 4 is for technical stakeholders — showing the Precision-Recall curve, ROC curve, and lift chart
> for the 527,813 final test observations."*

### Actions

1. **[POINT]** to PR-AUC curve: *"Area under this curve is 0.506 — the frozen Gate B2 metric."*
2. **[POINT]** to Top-K lift table: *"Top 5% gives 9.3× lift. Top 10% gives 6.6× lift."*
3. **[POINT]** to calibration reliability diagram: *"This shows how well predicted probabilities match observed repair rates across bins."*

---

## MINUTE 4:00 – 5:00 | Page 5 — Model Interpretation + Wrap-Up

### Navigation

- **[CLICK]** sidebar → `5 Model_Interpretation`

### Spoken Talking Points

> *"The final page provides the explainability layer. Prof. Amin — you can see the global SHAP rankings.
> Temperature features dominate — confirming that Montréal's freeze-thaw cycles are the primary statistical
> driver of recorded repair intervention patterns."*

### Actions

1. **[POINT]** to global SHAP bar chart: highlight `mean_temp_mean_30d` at rank #1, mean |φ| = 0.872.
2. **[POINT]** to repair history features at ranks #2–4.
3. **[SAY]:** *"Spearman ρ = 0.999946 across three independent sampling seeds — the rankings are not a sampling artifact."*
4. **[PAUSE]** — allow professor to ask initial question.

### Mandatory Closing Disclaimer

> *"One critical note before questions: all SHAP attributions describe historical statistical associations in
> Montréal's administrative repair records — they do not establish physical causal mechanisms. The system is
> a non-causal decision-support tool that informs, not mandates, maintenance planning decisions."*

---

## Emergency Contingency: Map Not Loading

If the Folium map fails to render:
1. **[CLICK]** browser refresh (F5)
2. **[WAIT]** 5 seconds
3. If still fails: navigate to Page 4 and show the statistical results — *"The dashboard is a visualization layer; our core contribution is the prediction engine and governance protocol."*

---

## Demo Timing Summary

| Time | Action |
|---|---|
| 0:00–0:45 | Hero landing → metric cards |
| 0:45–1:15 | Page 1 Executive Overview |
| 1:15–2:30 | Page 2 Interactive Risk Map ⭐ |
| 2:30–3:15 | Page 3 Segment Details |
| 3:15–4:00 | Page 4 Model Performance |
| 4:00–5:00 | Page 5 SHAP Interpretation + Closing disclaimer |
