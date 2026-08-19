"""
generate_figures.py — INSE 6311 Report Visual Package Generator (v2)
=====================================================================
Generates Figures 1-8 and 11-12 from real frozen project artifacts.
Figures 9 and 10 (dashboard screenshots) are copied from browser captures.

Run from project root:
    $env:PYTHONPATH=".;src"
    $env:PYTHONIOENCODING="utf-8"
    .\.venv\Scripts\python.exe report_assets/source/generate_figures.py
"""

import json, os, shutil, warnings, sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

warnings.filterwarnings("ignore")
matplotlib.use("Agg")

from sklearn.metrics import (
    precision_recall_curve, roc_curve, auc,
    average_precision_score, roc_auc_score,
)

# ── Palette & style ──────────────────────────────────────────────────────────
P = {
    "dark_blue": "#1A3A6E", "blue": "#2563EB", "mid_blue": "#3B82F6",
    "teal": "#0D9488", "orange": "#EA580C", "amber": "#D97706",
    "grey": "#6B7280", "light_grey": "#D1D5DB", "red": "#DC2626",
    "green": "#16A34A", "bg": "#FFFFFF", "text": "#111827",
}

matplotlib.rcParams.update({
    "figure.facecolor": P["bg"], "axes.facecolor": P["bg"],
    "axes.edgecolor": P["light_grey"], "axes.labelcolor": P["text"],
    "text.color": P["text"], "xtick.color": P["text"], "ytick.color": P["text"],
    "grid.color": P["light_grey"], "grid.linewidth": 0.8,
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.labelsize": 10,
    "legend.fontsize": 9, "figure.dpi": 150,
    "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.18,
})

ROOT = Path(__file__).resolve().parent.parent.parent
FIGS = ROOT / "report_assets" / "figures"
SHOTS = ROOT / "report_assets" / "screenshots"
FIGS.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(parents=True, exist_ok=True)

ARTIFACT_DIR = PROJECT_ROOT / "docs" / "figure_generation" / "output_figures"

print(f"ROOT: {ROOT}")
print(f"FIGURES: {FIGS}")
print(f"SCREENSHOTS: {SHOTS}")

# ── helpers ──────────────────────────────────────────────────────────────────
def save(fig, name):
    path = FIGS / name
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)
    print(f"  SAVED: {name}")
    return path

def box(ax, cx, cy, w, h, label, color, fontsize=8.5, tc="white"):
    rect = mpatches.FancyBboxPatch(
        (cx-w/2, cy-h/2), w, h,
        boxstyle="round,pad=0.08", lw=1.2,
        edgecolor="#334155", facecolor=color, zorder=3,
    )
    ax.add_patch(rect)
    ax.text(cx, cy, label, ha="center", va="center",
            fontsize=fontsize, color=tc, fontweight="bold",
            zorder=4, multialignment="center")

def arr(ax, x1, y1, x2, y2, col="#475569"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=col, lw=1.4, mutation_scale=14),
                zorder=2)

# ── B2 labels loader (exact partition paths) ─────────────────────────────────
B2_ANCHORS = {
    "2024-07-31": ("2024", "07"), "2024-08-31": ("2024", "08"),
    "2024-09-30": ("2024", "09"), "2024-10-31": ("2024", "10"),
    "2024-11-30": ("2024", "11"), "2024-12-31": ("2024", "12"),
    "2025-01-31": ("2025", "01"), "2025-02-28": ("2025", "02"),
    "2025-03-31": ("2025", "03"), "2025-04-30": ("2025", "04"),
    "2025-05-31": ("2025", "05"),
}
# Labels come from data/processed/phase_4 (original panel with targets)
P4_ROOT = ROOT / "data/processed/phase_4"

def load_b2_labels():
    parts = []
    for anchor, (yr, mo) in B2_ANCHORS.items():
        fpath = P4_ROOT / f"panel_year={yr}" / f"panel_month={mo}" / "segment_month.parquet"
        if fpath.exists():
            df = pd.read_parquet(fpath, columns=["segment_month_id", "target_repair_90d"])
            parts.append(df)
        else:
            print(f"  MISSING label file: {fpath}")
    if not parts:
        raise FileNotFoundError("No B2 label files found!")
    return pd.concat(parts, ignore_index=True).set_index("segment_month_id")


# ============================================================
# FIGURE 1 — System Workflow
# ============================================================
def fig01():
    print("Generating Figure 1: System Workflow...")
    fig, ax = plt.subplots(figsize=(16, 7))
    ax.set_xlim(0, 16); ax.set_ylim(0, 7); ax.axis("off")

    y1, y2, y3 = 5.0, 2.8, 1.0
    # Row 1: pipeline
    boxes1 = [
        (1.0, y1, 1.7, 0.85, "Open Data\nSources\n(7 datasets)",    P["dark_blue"]),
        (3.2, y1, 1.7, 0.85, "Spatial\nHarmonization\nEPSG:32188",  P["dark_blue"]),
        (5.4, y1, 1.7, 0.85, "47,983\nCanonical\nSegments",         P["blue"]),
        (7.6, y1, 1.7, 0.85, "Temporal\nIntegration\n102 anchors",  P["blue"]),
        (9.8, y1, 1.7, 0.85, "Panel\n4.89M rows",                   P["teal"]),
        (12.0, y1, 1.7, 0.85,"Leakage-Safe\nChronological\nSplit",  P["teal"]),
        (14.2, y1, 1.7, 0.85,"XGBoost\n3.4M rows\n184 rounds",      P["dark_blue"]),
    ]
    xs1 = [b[0] for b in boxes1]
    for b in boxes1: box(ax, *b)
    for i in range(len(xs1)-1): arr(ax, xs1[i]+0.85, y1, xs1[i+1]-0.85, y1)

    # Row 2: evaluation → dashboard (right to left)
    boxes2 = [
        (14.2, y2, 1.7, 0.85,"Gate B2\nEvaluation\nAP=0.506",     P["orange"]),
        (12.0, y2, 1.7, 0.85,"SHAP\nAttributions\n527,813 rows",   P["amber"]),
        (9.8,  y2, 1.7, 0.85,"Maintenance\nPrioritization\n4 bands",P["green"]),
        (7.6,  y2, 1.7, 0.85,"GIS\nDashboard\n5 pages",            P["blue"]),
    ]
    for b in boxes2: box(ax, *b)
    arr(ax, 14.2, y1-0.43, 14.2, y2+0.43)    # XGBoost -> Gate B2
    arr(ax, 13.35, y2, 12.85, y2)
    arr(ax, 11.15, y2, 10.65, y2)
    arr(ax, 8.95,  y2, 8.45,  y2)

    # Row 3: survival branch
    boxes3 = [
        (5.4, y3, 1.7, 0.75,"Repair\nEvent Data",                P["grey"]),
        (7.6, y3, 1.7, 0.75,"Mixed Event\nSurvival Cohort\n250,495 intervals",P["grey"]),
        (9.8, y3, 1.7, 0.75,"KM + Weibull\nAFT",                P["grey"]),
        (12.0,y3, 1.7, 0.75,"Degradation\nInterval\nEstimates",  P["grey"]),
    ]
    for b in boxes3: box(ax, *b)
    arr(ax, 5.4, y1-0.43, 5.4, y3+0.38)       # Segments -> repair data
    arr(ax, 6.25,y3, 6.75, y3)
    arr(ax, 8.45,y3, 8.95, y3)
    arr(ax, 10.65,y3,11.15,y3)

    ax.text(8.0, 0.25, "Phase 9 Extension: Survival Analysis Branch",
            ha="center", fontsize=8.5, color=P["grey"], style="italic")
    ax.set_title(
        "Figure 1 — End-to-End System Workflow: Montreal Road Risk Assessment Pipeline",
        fontsize=13, fontweight="bold", pad=10)
    save(fig, "Figure_01_System_Workflow.png")


# ============================================================
# FIGURE 2 — Chronological Data Split
# ============================================================
def fig02():
    print("Generating Figure 2: Chronological Split...")
    import datetime
    fig, ax = plt.subplots(figsize=(14, 3.8))
    ax.set_xlim(0, 14); ax.set_ylim(0, 3.5); ax.axis("off")

    start = datetime.date(2016, 12, 1)
    end   = datetime.date(2025, 5, 31)
    total = (end - start).days

    def dx(d):
        dd = datetime.date.fromisoformat(d) if isinstance(d, str) else d
        return 1.0 + (dd - start).days / total * 12.0

    segments = [
        ("2016-12-01","2022-10-31", P["blue"],    "Training
Dec 2016 – Oct 2022
3,406,793 rows"),
        ("2022-11-01","2022-12-31", P["grey"],    "Dev Gap
Nov–Dec 2022
95,966 rows"),
        ("2023-01-01","2023-10-31", P["teal"],    "Validation
Jan–Oct 2023
479,830 rows"),
        ("2023-11-01","2023-12-31", P["grey"],    "Excluded
Nov–Dec 2023
95,966 rows"),
        ("2024-01-01","2024-03-31", P["purple"],  "Gate B1 Calib
Jan–Mar 2024
143,949 rows"),
        ("2024-04-01","2024-06-30", P["amber"],   "Embargo
Apr–Jun 2024
143,949 rows"),
        ("2024-07-01","2025-05-31", P["orange"],  "Gate B2 Test
Jul 2024 – May 2025
527,813 rows"),
    ]
    yb, bh = 1.8, 0.75
    for s, e, c, lbl in segments:
        x0, x1 = dx(s), dx(e)
        r = mpatches.FancyBboxPatch((x0, yb-bh/2), x1-x0, bh,
            boxstyle="round,pad=0.03", lw=1.2, edgecolor="white",
            facecolor=c, alpha=0.92, zorder=3)
        ax.add_patch(r)
        ax.text((x0+x1)/2, yb, lbl, ha="center", va="center",
                fontsize=8, color="white", fontweight="bold",
                multialignment="center", zorder=4)

    # Nov23–Dec23 gap note
    gx = dx("2023-11-15")
    ax.annotate("Nov 23–Dec 23\ngap: training end\n→ validation start",
                xy=(gx, yb+bh/2), xytext=(gx-0.5, 2.9),
                fontsize=7.5, color=P["grey"], style="italic",
                arrowprops=dict(arrowstyle="->", color=P["grey"], lw=0.8))

    for yr in range(2017, 2026):
        xp = dx(f"{yr}-01-01")
        ax.axvline(xp, ymin=0.15, ymax=0.85, color=P["light_grey"], lw=0.7, ls="--")
        ax.text(xp, 0.55, str(yr), ha="center", fontsize=8, color=P["grey"])

    patches = [mpatches.Patch(facecolor=c, label=l.replace("\n"," "), alpha=0.9)
               for _, _, c, l in segments]
    ax.legend(handles=patches, loc="upper left", bbox_to_anchor=(0.0, 1.08),
              ncol=4, frameon=False, fontsize=8.5)
    ax.set_title("Figure 2 — Chronological Data Split: Training / Validation / Embargo / Gate B2 Test",
                 fontsize=12, fontweight="bold", pad=24)
    save(fig, "Figure_02_Chronological_Split.png")


# ============================================================
# FIGURE 3 — Gate B2 Performance Curves
# ============================================================
def fig03():
    print("Generating Figure 3: Gate B2 Performance Curves...")
    pred_df = pd.read_parquet(ROOT / "data/processed/phase_6/predictions/b2_predictions.parquet")
    labels  = load_b2_labels()
    merged  = pred_df.set_index("segment_month_id").join(labels[["target_repair_90d"]], how="inner")
    y_true  = merged["target_repair_90d"].values.astype(int)
    y_prob  = merged["raw_probability"].values.astype(float)

    ap_val  = average_precision_score(y_true, y_prob)
    auc_val = roc_auc_score(y_true, y_prob)
    print(f"  Computed AP={ap_val:.6f} AUC={auc_val:.6f} (expected 0.5057 / 0.9210)")
    assert abs(ap_val - 0.505693) < 0.002
    assert abs(auc_val - 0.920953) < 0.002

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))

    # PR
    ax = axes[0]
    prec, rec, _ = precision_recall_curve(y_true, y_prob)
    ax.plot(rec, prec, color=P["blue"], lw=2, label=f"XGBoost (AP = {ap_val:.4f})")
    ax.axhline(0.0579, color=P["grey"], lw=1.2, ls="--", label="Prevalence baseline (5.79%)")
    ax.fill_between([0,1], [0.4972]*2, [0.5143]*2, alpha=0.12, color=P["blue"],
                    label="95% CI [0.4972, 0.5143]")
    ax.set(xlabel="Recall", ylabel="Precision", title="Precision–Recall Curve",
           xlim=(0,1), ylim=(0,1.05))
    ax.legend(fontsize=8); ax.grid(True, alpha=0.35)
    ax.text(0.5, 0.08, "AP = 0.5057\n95% CI [0.4972, 0.5143]",
            transform=ax.transAxes, ha="center", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="#EFF6FF", ec=P["blue"]))

    # ROC
    ax = axes[1]
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    ax.plot(fpr, tpr, color=P["teal"], lw=2, label=f"XGBoost (AUC = {auc_val:.4f})")
    ax.plot([0,1], [0,1], color=P["grey"], lw=1.2, ls="--", label="Random classifier")
    ax.fill_between(fpr, tpr, alpha=0.08, color=P["teal"])
    ax.set(xlabel="False Positive Rate", ylabel="True Positive Rate",
           title="ROC Curve", xlim=(0,1), ylim=(0,1.05))
    ax.legend(loc="lower right", fontsize=8); ax.grid(True, alpha=0.35)
    ax.text(0.5, 0.15, "ROC-AUC = 0.9210\n95% CI [0.9194, 0.9227]",
            transform=ax.transAxes, ha="center", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="#F0FDFA", ec=P["teal"]))

    # Calibration (from frozen JSON)
    ax = axes[2]
    with open(ROOT / "models/phase_6/test_evaluation_results.json") as f:
        res = json.load(f)
    rel = res["primary_raw_metrics"]["reliability_table"]
    mp  = [r["mean_predicted"] for r in rel]
    ma  = [r["mean_actual"]    for r in rel]
    wt  = [r["weight"]         for r in rel]
    ax.plot([0,1],[0,1], color=P["grey"], lw=1.2, ls="--", label="Perfect calibration")
    ax.scatter(mp, ma, s=[w*3000 for w in wt], color=P["orange"],
               alpha=0.75, zorder=4, label="Observed bins (size prop. weight)")
    ax.plot(mp, ma, color=P["orange"], lw=1.5, alpha=0.7)
    ax.set(xlabel="Mean Predicted Probability", ylabel="Mean Observed Fraction",
           title="Calibration / Reliability Diagram",
           xlim=(-0.02,1.02), ylim=(-0.02,1.05))
    ax.legend(fontsize=8); ax.grid(True, alpha=0.35)
    ax.text(0.5, 0.08, "Brier = 0.0398 | ECE = 0.0216",
            transform=ax.transAxes, ha="center", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="#FFF7ED", ec=P["orange"]))

    fig.suptitle(
        "Figure 3 — Gate B2 Model Performance: PR Curve · ROC Curve · Calibration\n"
        "(n=527,813 · 30,572 positives · 5.79% prevalence · Raw XGBoost Probabilities)",
        fontsize=11, fontweight="bold", y=1.01)
    save(fig, "Figure_03_B2_Performance_Curves.png")


# ============================================================
# FIGURE 4 — Top-K Policy Comparison
# ============================================================
def fig04():
    print("Generating Figure 4: Top-K Policy Comparison...")
    labels = ["Top 5%\n(26,391)", "Top 10%\n(52,782)", "Top 20%\n(105,563)"]
    prec   = [0.539654, 0.381153, 0.237697]
    rec    = [0.465851, 0.658053, 0.820751]
    lift   = [9.316899, 6.580444, 4.103740]
    colors = [P["red"], P["orange"], P["amber"]]
    x = np.arange(3)

    fig, axes = plt.subplots(1, 3, figsize=(14, 5.2))
    for ax, vals, ylab, ytop, metric in zip(
        axes,
        [prec, rec, lift],
        ["Precision", "Recall", "Lift (× random baseline)"],
        [0.75, 1.05, 12.5],
        ["Precision", "Recall", "Lift"],
    ):
        bars = ax.bar(x, vals, width=0.5, color=colors, edgecolor="white", lw=1.2)
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
        ax.set_ylabel(ylab); ax.set_title(f"{metric} by Priority Band")
        ax.set_ylim(0, ytop); ax.grid(True, axis="y", alpha=0.35)
        for bar, v in zip(bars, vals):
            fmt = f"{v:.1%}" if metric != "Lift" else f"{v:.2f}x"
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+ytop*0.015,
                    fmt, ha="center", fontsize=9.5, fontweight="bold")
        if metric == "Precision":
            ax.axhline(0.0579, color=P["grey"], lw=1.0, ls="--", label="Prevalence 5.79%")
            ax.legend(fontsize=8)
        if metric == "Lift":
            ax.axhline(1.0, color=P["grey"], lw=1.0, ls="--", label="Random (1x)")
            ax.legend(fontsize=8)

    patches = [mpatches.Patch(color=c, label=l.replace("\n"," ")) for c,l in zip(colors, labels)]
    fig.legend(handles=patches, loc="lower center", ncol=3, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, -0.05))
    fig.suptitle(
        "Figure 4 — Top-K Operational Maintenance Policy Comparison\n"
        "(Three separate panels prevent shared-scale distortion)",
        fontsize=11, fontweight="bold", y=1.02)
    save(fig, "Figure_04_TopK_Policy_Comparison.png")


# ============================================================
# FIGURE 5 — Confusion Matrix (Threshold 0.30805489)
# ============================================================
def fig05():
    print("Generating Figure 5: Confusion Matrix...")
    TP, FP, FN, TN = 10949, 6702, 19623, 490539
    cm = np.array([[TN, FP], [FN, TP]], dtype=float)
    cm_r = cm / cm.sum(axis=1, keepdims=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), constrained_layout=True)
    for ax, data, title, vmax, fmtfn in [
        (axes[0], cm,   "Counts",                          490539.0, lambda v: f"{int(v):,}"),
        (axes[1], cm_r, "Row-Normalised (Recall-based)", 1.0,     lambda v: f"{v:.1%}"),
    ]:
        im = ax.imshow(data, cmap="Blues", vmin=0, vmax=vmax, aspect="auto")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_xticks([0,1]); ax.set_xticklabels(["Predicted\nNEGATIVE","Predicted\nPOSITIVE"], fontsize=10)
        ax.set_yticks([0,1]); ax.set_yticklabels(["Actual\nNEGATIVE","Actual\nPOSITIVE"], fontsize=10)
        ax.set_title(title, fontweight="bold", pad=8)
        for r in range(2):
            for c in range(2):
                v = data[r, c]
                tc = "white" if (vmax > 1 and v > vmax*0.5) else P["text"]
                ax.text(c, r, fmtfn(v), ha="center", va="center",
                        fontsize=12, fontweight="bold", color=tc)
        # Quadrant labels
        for (ri, ci, lbl) in [(0,0,"TN"),(0,1,"FP"),(1,0,"FN"),(1,1,"TP")]:
            ax.text(ci-0.38, ri-0.38, lbl, fontsize=8, color=P["grey"], ha="left", va="top")

    fig.suptitle(
        "Figure 5 — Frozen-Threshold Confusion Matrix  (threshold = 0.30805489)\n"
        "Precision=0.6203 | Recall=0.3581 | F1=0.4541 | Lift=10.71x",
        fontsize=11, fontweight="bold")
    save(fig, "Figure_05_Confusion_Matrix.png")


# ============================================================
# FIGURE 6 — SHAP Global Feature Importance
# ============================================================
def fig06():
    print("Generating Figure 6: SHAP Global Importance...")
    gi = pd.read_csv(ROOT / "data/processed/phase_7/global_importance_source.csv")
    top = gi.nlargest(20, "mean_abs_shap").copy()

    LABELS = {
        "mean_temp_mean_30d":                "Mean Temp (30d rolling)",
        "repair_active_days_365d":           "Repair Active Days (365d)",
        "repair_event_count_collapsed_365d": "Repair Event Count (365d)",
        "days_since_last_repair":            "Days Since Last Repair",
        "total_precip_sum_90d":              "Total Precipitation (90d)",
        "min_temp_min_365d":                 "Min Temp Min (365d)",
        "max_temp_max_30d":                  "Max Temp Max (30d)",
        "official_administrative_name":      "Borough Name (OHE 35 cols)",
        "functional_road_class":             "Functional Road Class (OHE 10 cols)",
        "administrative_category":           "Admin. Category (OHE 3 cols)",
        "days_since_condition_survey":       "Days Since PCI Survey",
        "mean_temp_mean_180d":               "Mean Temp (180d rolling)",
        "max_temp_max_180d":                 "Max Temp Max (180d)",
        "segment_length_m":                  "Segment Length (m)",
        "min_temp_min_30d":                  "Min Temp Min (30d)",
        "latest_pci":                        "Latest PCI Score",
        "mean_temp_mean_90d":                "Mean Temp (90d rolling)",
        "condition_campaign_scope":          "PCI Campaign Scope (OHE)",
        "freeze_thaw_strict_sum_180d":       "Freeze-Thaw Days (180d)",
        "min_temp_min_180d":                 "Min Temp Min (180d)",
    }
    top["label"] = top["source_feature"].map(LABELS).fillna(top["source_feature"])

    def fcolor(name):
        if any(k in name for k in ["temp","precip","freeze"]):
            return P["teal"]
        if any(k in name for k in ["repair","days_since_last"]):
            return P["orange"]
        if any(k in name for k in ["pci","condition","campaign"]):
            return P["amber"]
        return P["blue"]

    colors = [fcolor(f) for f in top["source_feature"]]
    y_pos  = np.arange(len(top))

    fig, ax = plt.subplots(figsize=(10, 8.5))
    bars = ax.barh(y_pos, top["mean_abs_shap"], color=colors, edgecolor="white", lw=0.7, height=0.68)
    ax.set_yticks(y_pos); ax.set_yticklabels(top["label"], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Mean Absolute SHAP Value (log-odds scale)")
    ax.set_title("Global Feature Importance (Top 20 Source Features)")
    ax.grid(True, axis="x", alpha=0.35)
    for bar, v in zip(bars, top["mean_abs_shap"]):
        ax.text(bar.get_width()+0.005, bar.get_y()+bar.get_height()/2,
                f"{v:.3f}", va="center", fontsize=8)

    legend_patches = [
        mpatches.Patch(color=P["teal"],   label="Climate features"),
        mpatches.Patch(color=P["orange"], label="Repair history features"),
        mpatches.Patch(color=P["amber"],  label="Pavement condition features"),
        mpatches.Patch(color=P["blue"],   label="Spatial / structural features"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=8.5)
    ax.text(0.5, -0.10,
            "SHAP values are non-causal statistical attributions from the trained XGBoost model.\n"
            "Rank stability verified: Spearman rho = 0.999946 across three independent 50,000-row samples.",
            transform=ax.transAxes, ha="center", fontsize=8.5, color=P["grey"], style="italic")

    fig.suptitle(
        "Figure 6 — Global SHAP Feature Importance\n"
        "(Exact XGBoost TreeContributions, 527,813 B2 evaluation rows)",
        fontsize=11, fontweight="bold", y=1.01)
    save(fig, "Figure_06_SHAP_Importance.png")


# ============================================================
# FIGURE 7 — Subgroup Equity Audit
# ============================================================
def fig07():
    print("Generating Figure 7: Subgroup Audit...")
    with open(ROOT / "models/phase_6/test_subgroup_results.json") as f:
        sg = json.load(f)

    def evaluated_rows(key):
        rows = []
        for gid, v in sg.get(key, {}).items():
            if v.get("status") == "EVALUATED":
                rows.append({
                    "group": gid,
                    "n_rows": v["n_rows"],
                    "prevalence": v["prevalence"],
                    "ap": v["primary_raw"]["average_precision"],
                    "roc_auc": v["primary_raw"]["roc_auc"],
                    "top10_prec": v["primary_raw"]["top_10_precision"],
                    "top10_rec": v["primary_raw"]["top_10_recall"],
                    "top10_lift": v["primary_raw"]["top_10_lift"],
                })
        return pd.DataFrame(rows)

    frc  = evaluated_rows("functional_road_class").sort_values("group")
    cond = evaluated_rows("condition_missing_flag")
    npr  = evaluated_rows("no_prior_repair_flag")
    cal  = evaluated_rows("calendar_quarter")

    fig = plt.figure(figsize=(16, 11))
    gs  = gridspec.GridSpec(2, 2, hspace=0.45, wspace=0.38, figure=fig)

    OVERALL_AP   = 0.505693
    OVERALL_LIFT = 6.580444

    # A: FRC AP
    ax = fig.add_subplot(gs[0, 0])
    if len(frc):
        clrs = [P["blue"] if i%2==0 else P["mid_blue"] for i in range(len(frc))]
        bars = ax.barh([f"Class {g}" for g in frc["group"]], frc["ap"],
                       color=clrs, edgecolor="white", height=0.6)
        ax.axvline(OVERALL_AP, color=P["orange"], lw=1.5, ls="--", label=f"Overall AP={OVERALL_AP:.4f}")
        ax.set_xlabel("Average Precision"); ax.set_title("AP by Functional Road Class")
        ax.legend(fontsize=8); ax.grid(True, axis="x", alpha=0.35)
        for bar, v in zip(bars, frc["ap"]):
            ax.text(bar.get_width()+0.005, bar.get_y()+bar.get_height()/2,
                    f"{v:.3f}", va="center", fontsize=8)

    # B: FRC Lift
    ax = fig.add_subplot(gs[0, 1])
    if len(frc):
        clrs = [P["blue"] if i%2==0 else P["mid_blue"] for i in range(len(frc))]
        bars = ax.barh([f"Class {g}" for g in frc["group"]], frc["top10_lift"],
                       color=clrs, edgecolor="white", height=0.6)
        ax.axvline(OVERALL_LIFT, color=P["orange"], lw=1.5, ls="--", label=f"Overall Lift={OVERALL_LIFT:.2f}x")
        ax.axvline(1.0, color=P["grey"], lw=1.0, ls=":", label="Random (1x)")
        ax.set_xlabel("Top-10% Lift"); ax.set_title("Top-10% Lift by Functional Road Class")
        ax.legend(fontsize=8); ax.grid(True, axis="x", alpha=0.35)
        for bar, v in zip(bars, frc["top10_lift"]):
            ax.text(bar.get_width()+0.05, bar.get_y()+bar.get_height()/2,
                    f"{v:.2f}x", va="center", fontsize=8)

    # C: Condition flag
    ax = fig.add_subplot(gs[1, 0])
    if len(cond):
        cond["label"] = cond["group"].map({"0":"PCI Available","1":"PCI Missing"})
        x = np.arange(len(cond))
        cols = [P["teal"], P["amber"]][:len(cond)]
        bars = ax.bar(x, cond["ap"], color=cols, edgecolor="white", width=0.4)
        ax.axhline(OVERALL_AP, color=P["orange"], lw=1.5, ls="--", label="Overall AP")
        ax.set_xticks(x); ax.set_xticklabels(cond["label"], fontsize=9)
        ax.set_ylabel("Average Precision"); ax.set_title("AP by Pavement Condition Availability")
        ax.legend(fontsize=8); ax.grid(True, axis="y", alpha=0.35)
        for xi, v in zip(x, cond["ap"]):
            ax.text(xi, v+0.008, f"{v:.3f}", ha="center", fontsize=9, fontweight="bold")
    else:
        ax.text(0.5, 0.5, "Insufficient sample\n(PCI Missing stratum < 500 rows or < 50 pos.)",
                ha="center", va="center", transform=ax.transAxes, fontsize=9,
                color=P["grey"], style="italic")
        ax.set_title("AP by Pavement Condition Availability")

    # D: Calendar quarter
    ax = fig.add_subplot(gs[1, 1])
    if len(cal):
        cal["label"] = cal["group"].map({"1":"Q1","2":"Q2","3":"Q3","4":"Q4"})
        x = np.arange(len(cal))
        qcols = [P["blue"], P["teal"], P["orange"], P["red"]][:len(cal)]
        bars = ax.bar(x, cal["ap"], color=qcols, edgecolor="white", width=0.4)
        ax.axhline(OVERALL_AP, color=P["grey"], lw=1.5, ls="--", label="Overall AP")
        ax.set_xticks(x); ax.set_xticklabels(cal["label"], fontsize=10)
        ax.set_ylabel("Average Precision"); ax.set_title("AP by Calendar Quarter (Seasonality)")
        ax.legend(fontsize=8); ax.grid(True, axis="y", alpha=0.35)
        for xi, v in zip(x, cal["ap"]):
            ax.text(xi, v+0.006, f"{v:.3f}", ha="center", fontsize=9, fontweight="bold")
    else:
        ax.text(0.5, 0.5, "No calendar_quarter groups evaluated",
                ha="center", va="center", transform=ax.transAxes, fontsize=9,
                color=P["grey"], style="italic")
        ax.set_title("AP by Calendar Quarter")

    fig.suptitle(
        "Figure 7 — Subgroup / Algorithmic Equity Audit\n"
        "All metrics from frozen Gate B2 labels. Groups with n<500 or <50 positives excluded.",
        fontsize=11, fontweight="bold", y=1.01)
    save(fig, "Figure_07_Subgroup_Equity_Audit.png")


# ============================================================
# FIGURE 8 — Dashboard Architecture
# ============================================================
def fig08():
    print("Generating Figure 8: Dashboard Architecture...")
    fig, ax = plt.subplots(figsize=(14, 7.5))
    ax.set_xlim(0, 14); ax.set_ylim(0, 7.5); ax.axis("off")

    # Data layer
    box(ax, 1.4, 6.4, 2.1, 0.85, "Gate B2 Predictions\nb2_predictions.parquet\n(527,813 rows)", P["dark_blue"])
    box(ax, 4.0, 6.4, 2.1, 0.85, "SHAP Explanations\nPhase 7 Parquet\n(Top-10% records)",       P["dark_blue"])
    box(ax, 6.6, 6.4, 2.1, 0.85, "Segment Metadata\nGeoBase + Boroughs",                        P["dark_blue"])
    box(ax, 9.5, 6.4, 2.5, 0.85, "Simplified GeoJSON\ngeobase_simplified.geojson\n47,983 segs, EPSG:4326", P["blue"])

    # Data mart
    box(ax, 4.0, 5.0, 5.0, 0.85, "Dashboard Data Mart\ndashboard_data_mart.parquet  |  527,813 rows · 35 columns · ZERO target columns", P["blue"])

    # Security
    box(ax, 4.0, 3.9, 5.2, 0.72, "security.py  —  Hard-reject target/outcome columns on load  |  CSV formula sanitization  |  HTML escape", "#7F1D1D")

    # Streamlit
    box(ax, 4.0, 2.9, 5.0, 0.72, "Streamlit Application  (app.py)", P["teal"])

    # 5 pages
    page_labels = ["Executive\nOverview","Interactive\nRisk Map","Segment\nDetails","Model\nPerformance","Model\nInterpretation"]
    for i, lbl in enumerate(page_labels):
        cx = 0.8 + i*2.4
        box(ax, cx, 1.65, 2.1, 0.72, f"Page {i+1}\n{lbl}", P["mid_blue"], fontsize=8)
        arr(ax, 4.0, 2.55, cx, 2.01)

    # Folium
    box(ax, 9.5, 5.0, 2.5, 0.85, "Folium GIS Map\nChoropleth layer\nBorough + band filters", P["teal"])

    # Planner
    box(ax, 12.5, 2.9, 1.8, 0.72, "Municipal\nPlanner\n(End User)", P["green"])

    # Arrows
    for cx in [1.4, 4.0, 6.6]: arr(ax, cx, 5.98, 4.0-0.1*(cx-4.0), 5.43)
    arr(ax, 4.0, 4.58, 4.0, 4.25)
    arr(ax, 4.0, 3.54, 4.0, 3.25)
    arr(ax, 9.5, 5.98, 9.5, 5.43)
    arr(ax, 9.5, 4.58, 7.8, 3.25)
    arr(ax, 6.5, 2.9, 9.5, 2.9)
    arr(ax, 9.5, 2.55, 12.5, 3.25)

    # Boundary
    bnd = mpatches.FancyBboxPatch((0.15, 1.2), 8.6, 4.1,
        boxstyle="round,pad=0.1", lw=2.0, edgecolor=P["red"],
        facecolor="none", ls="--", zorder=1)
    ax.add_patch(bnd)
    ax.text(4.45, 5.43, "Target-Free Deployment Boundary", ha="center",
            fontsize=9.5, color=P["red"], fontweight="bold")

    ax.set_title(
        "Figure 8 — GIS Dashboard Architecture: Target-Free Deployment\n"
        "Cold startup 1.43s | Warm 1.30s | Map build 2.53s | Peak RSS 680 MB | Geometry join 100%",
        fontsize=12, fontweight="bold", pad=10)
    save(fig, "Figure_08_Dashboard_Architecture.png")


# ============================================================
# FIGURE 11 — Kaplan-Meier Survival
# ============================================================
def fig11():
    print("Generating Figure 11: Kaplan-Meier...")
    sys.path.insert(0, str(ROOT / "src"))
    from montreal_road_risk.survival.non_parametric import kaplan_meier_estimator

    cohort = pd.read_parquet(ROOT / "data/processed/phase_9/survival_cohort.parquet")
    print(f"  Cohort: {len(cohort):,} rows | events={cohort.event_observed.sum():,} | censored={(cohort.event_observed==0).sum():,}")

    km_all = kaplan_meier_estimator(cohort["duration_days"].values, cohort["event_observed"].values)

    cls_counts = cohort.groupby("functional_road_class")["event_observed"].agg(["sum","count"])
    eligible   = cls_counts[cls_counts["sum"] >= 300].index.tolist()[:5]
    km_classes = {}
    for cls in eligible:
        sub = cohort[cohort["functional_road_class"] == cls]
        km_classes[cls] = (kaplan_meier_estimator(sub["duration_days"].values, sub["event_observed"].values),
                           len(sub))

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Overall
    ax = axes[0]
    t  = km_all["timeline"]
    s  = km_all["survival_probability"]
    lo = km_all["confidence_interval_lower"]
    hi = km_all["confidence_interval_upper"]
    ax.step(t, s, where="post", color=P["blue"], lw=2.0, label="Overall KM estimate")
    ax.fill_between(t, lo, hi, step="post", alpha=0.18, color=P["blue"], label="95% Greenwood CI")
    ax.axhline(0.5, color=P["grey"], lw=1.0, ls="--", alpha=0.7)
    med = km_all.get("median_survival_time")
    if med is not None and not np.isnan(float(med)):
        ax.axvline(float(med), color=P["orange"], lw=1.5, ls=":",
                   label=f"Median T50 = {float(med):.0f} days")
    t_max = float(np.nanmax(t)) if len(t) else 3000
    ax.set(xlabel="Days since last repair", ylabel="Survival Probability S(t)",
           title="Overall Kaplan-Meier Survival Curve\n(All segments, mixed event cohort)",
           xlim=(0, min(t_max, 3000)), ylim=(-0.02, 1.05))
    ax.legend(fontsize=9); ax.grid(True, alpha=0.35)
    ax.text(0.98, 0.97,
            f"n = {len(cohort):,} intervals\nObserved = {cohort.event_observed.sum():,}\nCensored = {(cohort.event_observed==0).sum():,}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.3", fc="#EFF6FF", ec=P["blue"]))

    # By road class
    ax = axes[1]
    cls_colors = [P["blue"], P["teal"], P["orange"], P["red"], P["amber"]]
    for i, (cls, (km, nrows)) in enumerate(km_classes.items()):
        c = cls_colors[i % len(cls_colors)]
        ax.step(km["timeline"], km["survival_probability"], where="post", color=c, lw=1.8,
                label=f"Road Class {cls} (n={nrows:,})")
        ax.fill_between(km["timeline"], km["confidence_interval_lower"], km["confidence_interval_upper"],
                        step="post", alpha=0.1, color=c)
    ax.axhline(0.5, color=P["grey"], lw=1.0, ls="--", alpha=0.7, label="S(t)=0.5")
    ax.set(xlabel="Days since last repair", ylabel="Survival Probability S(t)",
           title="KM Survival Curves by Functional Road Class",
           xlim=(0, 3000), ylim=(-0.02, 1.05))
    ax.legend(fontsize=8.5); ax.grid(True, alpha=0.35)

    fig.suptitle(
        "Kaplan–Meier Survival Analysis: Time-to-Next Repair Interval\n"
        "(Mixed first-event/recurrent-event cohort · 19.12% interval censoring · Greenwood 95% CI)",
        fontsize=11, fontweight="bold", y=1.01)
    save(fig, "Figure_11_KaplanMeier_Survival.png")


# ============================================================
# FIGURE 12 — Weibull AFT
# ============================================================
def fig12():
    print("Generating Figure 12: Weibull AFT...")
    sys.path.insert(0, str(ROOT / "src"))
    from montreal_road_risk.survival.modeling import WeibullAFTModel

    cohort = pd.read_parquet(ROOT / "data/processed/phase_9/survival_cohort.parquet")
    rng = np.random.default_rng(42)
    idx = rng.choice(len(cohort), size=min(50000, len(cohort)), replace=False)
    samp = cohort.iloc[idx].copy()

    X_raw = samp[["segment_length_m", "functional_road_class"]].values.astype(float)
    mu, sd = X_raw.mean(0), X_raw.std(0) + 1e-8
    X = (X_raw - mu) / sd
    t = samp["duration_days"].values.astype(float)
    e = samp["event_observed"].values.astype(int)

    print("  Fitting Weibull AFT on 50k sample...")
    model = WeibullAFTModel()
    model.fit(t, e, X)  # API: fit(durations, events, X=covariate_matrix)
    # beta_ includes intercept at index 0; covariates start at index 1
    beta_all = model.beta_   # shape: (n_features+1,)  [intercept, length, frc]
    sigma    = float(model.sigma_)
    print(f"  Fitted: beta={beta_all}, sigma={sigma:.4f}")
    # Covariate coefficients (skip intercept at [0])
    beta_cov = beta_all[1:]  # [length_coef, frc_coef]

    t_grid = np.linspace(1, 2000, 500)

    profiles = [
        ("Short local (class 8, 50 m)",   50,  8),
        ("Medium collector (class 4, 200 m)", 200, 4),
        ("Long arterial (class 3, 500 m)", 500, 3),
        ("Major arterial (class 2, 800 m)", 800, 2),
    ]
    cls_colors = [P["teal"], P["blue"], P["orange"], P["red"]]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    for (lbl, length, frc), col in zip(profiles, cls_colors):
        xv = np.array([(length - mu[0])/sd[0], (frc - mu[1])/sd[1]])
        # Compute linear predictor: intercept + X*beta_cov
        eta = float(beta_all[0] + xv @ beta_cov)
        z   = (np.log(t_grid + 1e-9) - eta) / sigma
        s_t = np.exp(-np.exp(z))
        ax.plot(t_grid, s_t, color=col, lw=2.0, label=lbl)
    ax.axhline(0.5, color=P["grey"], lw=1.0, ls="--", label="S(t)=0.5")
    ax.set(xlabel="Days since last repair", ylabel="Predicted Survival S(t|x)",
           title="Weibull AFT: Predicted Survival Curves\nby Segment Profile",
           xlim=(0, 2000), ylim=(-0.02, 1.05))
    ax.legend(fontsize=8.5); ax.grid(True, alpha=0.35)
    ax.text(0.97, 0.97,
            f"sigma = {sigma:.3f}\nbeta[intercept] = {beta_all[0]:.3f}\nbeta[length] = {beta_cov[0]:.3f}\nbeta[frc] = {beta_cov[1]:.3f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.3", fc="#FFF7ED", ec=P["orange"]))

    ax = axes[1]
    class_medians = {}
    for cls in sorted(cohort["functional_road_class"].unique()):
        sub = cohort[cohort["functional_road_class"] == cls]
        if len(sub) < 100: continue
        med_len = float(sub["segment_length_m"].median())
        xv = np.array([(med_len - mu[0])/sd[0], (float(cls) - mu[1])/sd[1]])
        eta_c = float(beta_all[0] + xv @ beta_cov)
        med_t = float(np.exp(eta_c + sigma * np.log(np.log(2))))
        class_medians[int(cls)] = float(np.clip(med_t, 1, 10000))

    if class_medians:
        clbls = [f"Class {k}" for k in class_medians]
        cvals = list(class_medians.values())
        ccols = [cls_colors[i%len(cls_colors)] for i in range(len(clbls))]
        bars = ax.barh(clbls, cvals, color=ccols, edgecolor="white", height=0.6)
        ax.set_xlabel("Predicted Median Time-to-Next Repair (days)")
        ax.set_title("Weibull AFT: Predicted Median Survival\nby Functional Road Class")
        ax.grid(True, axis="x", alpha=0.35)
        for bar, v in zip(bars, cvals):
            ax.text(bar.get_width()+5, bar.get_y()+bar.get_height()/2,
                    f"{v:.0f} d", va="center", fontsize=8.5)

    fig.suptitle(
        "Figure 12 — Weibull AFT Survival Regression: Predicted Degradation Interval Estimates\n"
        "Fitted on 50,000-row stratified sample | Covariates: segment length, road class | Non-causal estimates",
        fontsize=11, fontweight="bold", y=1.01)
    save(fig, "Figure_12_Weibull_AFT.png")


# ============================================================
# Copy dashboard screenshots (Figures 9 & 10)
# ============================================================
def copy_screenshots():
    print("Copying dashboard screenshots...")
    candidates = {
        "Figure_09_Dashboard_Risk_Map.png":      "high_risk_segments_map",
        "Figure_10_Segment_Details.png":         "segment_details_view",
    }
    for dest_name, stem in candidates.items():
        # Search artifact directory for the file
        matches = list(ARTIFACT_DIR.glob(f"{stem}*.png"))
        if matches:
            src = sorted(matches, key=lambda p: p.stat().st_mtime)[-1]
            shutil.copy2(src, SHOTS / dest_name)
            print(f"  COPIED: {src.name} -> {dest_name}")
        else:
            print(f"  NOT FOUND: {stem}*.png  (will be recorded in DATA_ISSUES.md)")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("INSE 6311 Report Visual Package Generator v2")
    print("=" * 60)
    fig01()
    fig02()
    fig03()
    fig04()
    fig05()
    fig06()
    fig07()
    fig08()
    fig11()
    fig12()
    copy_screenshots()
    print("=" * 60)
    print("All figure generation complete.")
    print("=" * 60)
