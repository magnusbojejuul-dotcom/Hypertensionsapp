import math
from typing import Dict, Optional, Tuple, List
import streamlit as st
import pandas as pd
import numpy as np

# -----------------------------
# APP CONFIG
# -----------------------------
st.set_page_config(
    page_title="Hypertension & SCORE2 — Lægerne i Lind",
    page_icon="💊",
    layout="wide"
)

# -----------------------------
# HEADER
# -----------------------------
st.markdown(
    "<h1 style='text-align: center;'>💊 Lægerne i Lind – Hypertension beslutningsstøtte</h1>",
    unsafe_allow_html=True
)
st.caption("Undervisningsprototype. Verificér altid mod gældende retningslinjer (DSAM/SST/ESC).")
st.markdown("---")

# -----------------------------
# SIDEBAR: Forkortelser + links + eksempler
# -----------------------------
with st.sidebar:
    st.header("🔍 Forkortelser")
    st.write("**ACE-hæmmer**: Angiotensin Converting Enzyme-hæmmer")
    st.write("**ARB**: Angiotensin II receptorblokker")
    st.write("**CCB**: Calciumkanalblokker")
    st.write("**DHP**: Dihydropyridin (type af CCB)")
    st.write("**MRA**: Mineralokortikoid-receptorantagonist")
    st.write("**RAAS**: Renin–Angiotensin–Aldosteron-System")
    st.write("**AF**: Atrieflimren")
    st.write("**CKD**: Kronisk nyresygdom")

    st.markdown("---")
    st.write("[Lægehåndbogen – Hypertension](https://www.sundhed.dk/sundhedsfaglig/laegehaandbogen/hjerte-kar/tilstande-og-sygdomme/blodtryk/hypertension/)")
    st.write("[DSAM – Hypertension](https://www.dsam.dk)")
    st.write("[ESC SCORE2 (EHJ 2021)](https://academic.oup.com/eurheartj/article/42/25/2439/6297709)")

    st.markdown("---")
    st.subheader("📄 Eksempler")
    load_examples = st.button("Indlæs example_patients.csv")

# -----------------------------
# LOAD DATA FILES (cache)
# -----------------------------
@st.cache_data
def load_csv_or_none(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return None

coeff_df = load_csv_or_none("score2_coefficients.csv")
baseline_df = load_csv_or_none("score2_baseline.csv")

# fallback – hvis CSV ikke findes endnu
COEFFS_FALLBACK = pd.DataFrame({
    "sex": ["M","M","M","M","M","M","M","M","M","M",
            "F","F","F","F","F","F","F","F","F","F"],
    "term": ["cage","csbp","ctc","chdl","smoke","cage*csbp","cage*ctc","cage*chdl","cage*smoke","cage*smoke",
             "cage","csbp","ctc","chdl","smoke","cage*csbp","cage*ctc","cage*chdl","cage*smoke","cage*smoke"],
    "coef": [0.3742,0.2777,0.1458,-0.2698,0.6012,-0.0255,-0.0281,0.0426,-0.0755,-0.0755,
             0.4648,0.3131,0.1002,-0.2606,0.7744,-0.0277,-0.0226,0.0613,-0.1088,-0.1088]
})
BASELINE_FALLBACK = pd.DataFrame({
    "sex":["M","F"],
    "region":["NorthernEurope","NorthernEurope"],
    "s0_10y":[0.9605,0.9776],
    "scale1":[-0.5699,-0.7380],
    "scale2":[0.7476,0.7019]
})

if coeff_df is None:
    coeff_df = COEFFS_FALLBACK.copy()
if baseline_df is None:
    baseline_df = BASELINE_FALLBACK.copy()

# -----------------------------
# Hjælpefunktioner
# -----------------------------
def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def age_adjusted_refs(age: int) -> Dict[str, Tuple[float, float]]:
    # simple, pædagogiske aldersjusteringer (kan tilpasses lokale refs)
    na_low, na_high = 137.0, 145.0
    k_low, k_high = 3.5, 5.0
    egfr_high = 120.0
    if age >= 70:
        na_low -= 0.5; na_high -= 0.5; k_high += 0.1
    if age >= 80:
        na_low -= 0.5; na_high -= 0.5; k_high += 0.1
    expected = egfr_high if age <= 40 else max(60.0, egfr_high - (age - 40) * 1.0)
    egfr_low = 60.0
    return {"na": (na_low, na_high), "k": (k_low, k_high), "egfr": (egfr_low, expected), "urate": (0.20, 0.42)}

def outside(ref: Tuple[float, float], val: Optional[float]) -> bool:
    if val is None: return False
    lo, hi = ref
    return val < lo or val > hi

# -----------------------------
# SCORE2 beregner (CSV-drevet)
# -----------------------------
def calculate_score2(age: int, sex_label: str, sbp: float, tc: float, hdl: float, smoker_label: str) -> Optional[float]:
    sex_code = "M" if sex_label.startswith("M") else "F"
    df = coeff_df[coeff_df["sex"].str.upper().str[0] == sex_code]
    if df.empty:
        return None

    cage = (age - 60) / 5.0
    csbp = (sbp - 120) / 20.0
    ctc = (tc - 6.0) / 1.0
    chdl = (hdl - 1.3) / 0.5
    csmoke = 1.0 if smoker_label == "Ja" else 0.0

    lp = 0.0
    for _, row in df.iterrows():
        term = str(row["term"]).lower()
        coef = float(row["coef"])
        if term == "cage":
            lp += coef * cage
        elif term == "csbp":
            lp += coef * csbp
        elif term in ("ctc","ctchol"):
            lp += coef * ctc
        elif term == "chdl":
            lp += coef * chdl
        elif term in ("smoke","current_smoker"):
            lp += coef * csmoke
        elif term in ("cage*csbp","cage_csbp"):
            lp += coef * cage * csbp
        elif term in ("cage*ctc","cage_ctchol"):
            lp += coef * cage * ctc
        elif term in ("cage*chdl","cage_chdl"):
            lp += coef * cage * chdl
        elif term in ("cage*smoke","cage_smoker"):
            lp += coef * cage * csmoke

    base = baseline_df[
        (baseline_df["sex"].str.upper().str[0] == sex_code) &
        (baseline_df["region"].str.lower().isin(["northerneurope","low","low-risk","nordeuropa"]))
    ]
    if base.empty:
        base = baseline_df[baseline_df["sex"].str.upper().str[0] == sex_code]
    if base.empty:
        return None

    s0 = float(base.iloc[0]["s0_10y"])
    scale1 = float(base.iloc[0]["scale1"])
    scale2 = float(base.iloc[0]["scale2"])

    # uncalibrated + calibration (ESC)
    risk_uncal = 1.0 - math.exp(math.log(s0) * math.exp(lp))
    risk_uncal = clamp(risk_uncal, 1e-9, 0.999999)
    try:
        ln_negln = math.log(-math.log(1.0 - risk_uncal))
        risk_cal = 1.0 - math.exp(-math.exp(scale1 + scale2 * ln_negln))
    except Exception:
        return None
    return float(100.0 * clamp(risk_cal, 0.0, 0.9999))

def risk_category(score2_pct: Optional[float], age: int) -> Tuple[str, str]:
    if score2_pct is None: return "Ukendt", "gray"
    r = score2_pct
    if 40 <= age <= 49: cuts = (2.5, 7.5)
    elif 50 <= age <= 59: cuts = (5.0, 10.0)
    elif 60 <= age <= 69: cuts = (7.5, 15.0)
    else: cuts = (10.0, 20.0)
    low, high = cuts
    if r < low: return "Lav risiko", "green"
    elif r < high: return "Moderat risiko", "orange"
    else: return "Høj/Meget høj risiko", "red"

# -----------------------------
# EKSEMPEL-DATA (indlæs)
# -----------------------------
if load_examples:
    try:
        df_ex = pd.read_csv("example_patients.csv")
        st.session_state["examples"] = df_ex.to_dict(orient="records")
        st.sidebar.success(f"Indlæst {len(df_ex)} eksempler.")
    except Exception as e:
        st.sidebar.error(f"Kunne ikke indlæse eksempler: {e}")

example = None
if "examples" in st.session_state and st.session_state["examples"]:
    names = [r.get("navn","Case") for r in st.session_state["examples"]]
    choice = st.sidebar.selectbox("Vælg eksempel", ["(Ingen)"] + names)
    if choice != "(Ingen)":
        example = next(r for r in st.session_state["examples"] if r.get("navn","Case")==choice)

# -----------------------------
# PATIENT-INPUTS
# -----------------------------
st.header("1) Patientoplysninger")
colA, colB, colC = st.columns(3)
with colA:
    alder = st.number_input("Alder (år)", 18, 95, int(example["alder"]) if example else 58)
    koen = st.selectbox("Køn", ["Mand","Kvinde"], index=(0 if not example else (0 if example.get("køn","M")=="Mand" else 1)))
    ryger = st.selectbox("Ryger", ["Nej","Ja"], index=(1 if (example and example.get("ryger","Nej")=="Ja") else 0))
with colB:
    sbp = st.number_input("Systolisk BT (mmHg)", 80, 250, int(example["sbp"]) if example else 150)
    tc = st.number_input("Total-kolesterol (mmol/L)", 2.0, 12.0, float(example["tchol"]) if example else 5.8, step=0.1, format="%.1f")
with colC:
    hdl = st.number_input("HDL (mmol/L)", 0.5, 4.0, float(example["hdl"]) if example else 1.3, step=0.1, format="%.1f")
    st.write("**Komorbiditeter/forhold**")
    diabetes = st.checkbox("Diabetes", value=(example.get("diabetes","Nej")=="Ja") if example else False)
    ckd = st.checkbox("CKD/kronisk nyresygdom", value=(example.get("ckd","Nej")=="Ja") if example else False)
    proteinuria = st.checkbox("Betydende albuminuri/proteinuri", value=(example.get("proteinuri","Nej")=="Ja") if example else False)
    cad = st.checkbox("Iskæmisk hjertesygdom", value=(example.get("cad","Nej")=="Ja") if example else False)
    heart_failure = st.checkbox("Hjertesvigt", value=(example.get("hf","Nej")=="Ja") if example else False)
    af = st.checkbox("Atrieflimren", value=(example.get("af","Nej")=="Ja") if example else False)
    stroke_tia = st.checkbox("Apopleksi/TIA", value=(example.get("stroke_tia","Nej")=="Ja") if example else False)
    pregnancy = st.checkbox("Graviditet", value=False)
    gout = st.checkbox("Urin-syregigt", value=(example.get("gigt","Nej")=="Ja") if example else False)
    asthma_copd = st.checkbox("Astma/COPD", value=(example.get("astma_copd","Nej")=="Ja") if example else False)
    edema = st.checkbox("Tendens til perifere ødemer", value=(example.get("ødem","Nej")=="Ja") if example else False)

# -----------------------------
# LABS
# -----------------------------
st.header("2) Væsketal/elektrolytter")
refs = age_adjusted_refs(int(alder))
c1, c2, c3, c4 = st.columns(4)
with c1:
    na = st.number_input(f"Na⁺ (mmol/L) — ref {refs['na'][0]:.1f}–{refs['na'][1]:.1f}", 110.0, 170.0, float(example.get("na",138)) if example else 138.0, step=0.1)
with c2:
    k = st.number_input(f"K⁺ (mmol/L) — ref {refs['k'][0]:.1f}–{refs['k'][1]:.1f}", 2.0, 7.0, float(example.get("k",4.2)) if example else 4.2, step=0.1)
with c3:
    egfr = st.number_input(f"eGFR (mL/min/1.73m²) — ref {refs['egfr'][0]:.0f}–{refs['egfr'][1]:.0f}", 5.0, 200.0, float(example.get("egfr",85)) if example else 85.0, step=1.0)
with c4:
    urate = st.number_input(f"Urat (mmol/L) — ref {refs['urate'][0]:.2f}–{refs['urate'][1]:.2f}", 0.05, 2.0, float(example.get("urat",0.35)) if example else 0.35, step=0.01)

alerts = []
if outside(refs["na"], na): alerts.append("Na⁺ uden for reference — vurder årsag; undgå tiazider ved hyponatriæmi.")
if outside(refs["k"], k): alerts.append("K⁺ uden for reference — RAAS/MRA kan give hyperkaliæmi.")
if egfr < refs["egfr"][0]: alerts.append("eGFR under reference — tiazider mindre effektive ved eGFR<30; pas på RAAS/MRA.")
if outside(refs["urate"], urate): alerts.append("Urat forhøjet — tiazider kan forværre urinsyregigt.")
if alerts:
    st.warning("**Elektrolyt/nyrefunktion — opmærksomhedspunkter:**\n\n- " + "\n- ".join(alerts))

# -----------------------------
# SCORE2
# -----------------------------
st.header("3) SCORE2")
colL, colR = st.columns([2,1])
with colL:
    st.caption("Beregnes automatisk ud fra dine CSV-filer. (Fallback indbygget hvis CSV mangler).")
with colR:
    manual_score2 = st.number_input("Manuel SCORE2 % (fallback)", 0.0, 100.0, 7.0, step=0.1)

auto_score2 = calculate_score2(int(alder), koen, float(sbp), float(tc), float(hdl), ryger)
score2_final = auto_score2 if auto_score2 is not None else manual_score2

cat, color = risk_category(score2_final, int(alder))
rc1, rc2 = st.columns([1,3])
with rc1:
    st.metric("SCORE2 (10 år)", f"{score2_final:.1f}%" if score2_final is not None else "—")
with rc2:
    ridx = {"green":"🟢","orange":"🟠","red":"🔴","gray":"⚪"}.get(color,"🟢")
    st.markdown(f"### {ridx} {cat}")

# Diabetes-advarsel
if diabetes:
    st.warning(
        "**Bemærk: SCORE2 er ikke tiltænkt personer med diabetes.**\n\n"
        "- Diabetes medfører høj/ meget høj kardiovaskulær risiko, som SCORE2 ikke afspejler korrekt.\n"
        "- Brug diabetes-specifik vurdering og ESC-behandlingsmål for høj risiko."
    )

# -----------------------------
# INTERAKTIONER (andre præparater der kan give problemer)
# -----------------------------
st.header("4) Andre præparater — interaktionstjek")
st.caption("Marker hvis patienten samtidig får nedenstående præparater (interaktion/kontraindikation).")
interaction_defs = {
    "Lithium": {"avoid": ["ACE-hæmmer","ARB","Tiazid(-lign.) diuretikum"], "why": "Øget lithium-niveau og toksicitet."},
    "NSAID (fast)": {"avoid": ["ACE/ARB + diuretikum (kombination)"], "why": "Øget risiko for AKI ('triple whammy')."},
    "Verapamil/diltiazem": {"avoid": ["Beta-blokker"], "why": "Risiko for AV-blok/bradykardi i kombination."},
    "Kaliumtilskud/K+-spare": {"avoid": ["MRA (spironolakton/eplerenon)","ACE-hæmmer","ARB"], "why": "Hyperkaliæmi-risiko."},
    "Prednisolon (høj dosis)": {"caution": ["Diuretika"], "why": "Væskeretention; kan modvirke antihypertensiv effekt."},
}
icol1, icol2, icol3 = st.columns(3)
interaction_state = {}
for i, drug in enumerate(interaction_defs.keys()):
    with [icol1, icol2, icol3][i % 3]:
        interaction_state[drug] = st.checkbox(drug, value=False)

# -----------------------------
# MEDICIN-VALG (typiske antihypertensiva)
# -----------------------------
st.header("5) Valgt/overvejet antihypertensiv behandling")
med_options = [
    "ACE-hæmmer",
    "ARB",
    "DHP-CCB (amlodipin)",
    "Tiazid-lignende diuretikum",
    "Beta-blokker",
    "MRA (spironolakton/eplerenon)",
]
chosen_meds = st.multiselect("Vælg de klasser, du overvejer/pt. bruger", med_options, default=[])

# -----------------------------
# KONTRAINDIKATIONSTJEK + PLAN B
# -----------------------------
def check_contras_and_plan(
    chosen: List[str],
    diabetes: bool, ckd: bool, proteinuria: bool, cad: bool, heart_failure: bool,
    af: bool, stroke_tia: bool, pregnancy: bool, asthma_copd: bool, edema: bool, gout: bool,
    na: float, k: float, egfr: float, urate: float,
    interactions_checked: Dict[str, bool]
):
    avoid = []
    rationale = []

    # labs/tilstande
    if k >= 5.0:
        avoid += ["ACE-hæmmer","ARB","MRA (spironolakton/eplerenon)"]
        rationale.append("Hyperkaliæmi: undgå RAAS/MRA indtil korrigeret.")
    if na < 133.0:
        avoid += ["Tiazid-lignende diuretikum"]
        rationale.append("Hyponatriæmi: tiazider kan forværre.")
    if egfr < 30.0:
        avoid += ["Tiazid-lignende diuretikum (ineffektiv ved eGFR<30)","MRA (spironolakton/eplerenon) (forsigtighed)"]
        rationale.append("Lav eGFR: brug loop-diuretikum ved volumenoverload; forsigtighed med MRA.")
    if gout or urate > 0.42:
        avoid += ["Tiazid-lignende diuretikum"]
        rationale.append("Urinsyregigt: tiazider øger urinsyre.")
    if pregnancy:
        avoid += ["ACE-hæmmer","ARB","MRA (spironolakton/eplerenon)"]
        rationale.append("Graviditet: undgå RAAS/MRA; brug labetalol, nifedipin (retard) eller methyldopa.")
    if asthma_copd and "Beta-blokker" in chosen:
        rationale.append("Astma/COPD: undgå ikke-selektive beta-blokkere; brug selektiv eller undlad.")

    # interaktioner
    for drug, on in interactions_checked.items():
        if not on: continue
        info = interaction_defs.get(drug,{})
        if "avoid" in info:
            avoid += info["avoid"]
        if "caution" in info:
            avoid += info["caution"]
        why = info.get("why")
        if why:
            rationale.append(f"Interaktion ({drug}): {why}")

    # dedup
    seen=set(); avoid_u=[]
    for x in avoid:
        if x not in seen:
            avoid_u.append(x); seen.add(x)

    # Plan B (simpel regel)
    plan_b = []
    if any(x in avoid_u for x in ["ACE-hæmmer","ARB"]):
        plan_b += ["DHP-CCB (amlodipin) + Tiazid-lignende diuretikum"]
    if "Tiazid-lignende diuretikum" in avoid_u:
        plan_b += ["ACE/ARB + DHP-CCB", "Overvej loop-diuretikum ved volumenoverload"]
    if pregnancy:
        plan_b = ["Labetalol", "Nifedipin (retard)", "Methyldopa"]

    # Førstevalg ift. CKD/proteinuri/diabetes
    first_line_notes = []
    if (ckd or proteinuria) and not pregnancy:
        first_line_notes.append("CKD/albuminuri: ACE-hæmmer ELLER ARB (nefroprotektion).")
    if diabetes and not pregnancy:
        first_line_notes.append("Diabetes: RAAS-blokade ofte grundstammen; monitorér K+/kreatinin.")

    return avoid_u, rationale, plan_b, first_line_notes

avoid_list, rationale_list, plan_b_list, first_line_notes = check_contras_and_plan(
    chosen_meds, diabetes, ckd, proteinuria, cad, heart_failure, af, stroke_tia, pregnancy,
    asthma_copd, edema, gout, float(na), float(k), float(egfr), float(urate), interaction_state
)

colL, colR = st.columns(2)
with colL:
    st.subheader("🔧 Forslag / førstevalg (noter)")
    if first_line_notes:
        for x in first_line_notes:
            st.success(x)
    else:
        st.write("- (ingen særlige noter)")

with colR:
    st.subheader("⛔ Undgå / forsigtighed")
    if avoid_list:
        for x in avoid_list:
            st.error(f"- {x}")
    else:
        st.write("- (ingen specifikke)")

st.subheader("📋 Begrundelser (kort)")
if rationale_list:
    for x in rationale_list:
        st.write(f"- {x}")
else:
    st.write("- (ingen)")

st.subheader("🧭 Plan B")
if plan_b_list:
    for x in plan_b_list:
        st.warning(f"- {x}")
else:
    st.write("- (ingen)")

# -----------------------------
# SIMULER ÆNDRING
# -----------------------------
st.header("6) Simulér ændring")
st.caption("Juster en parameter og se ændring i SCORE2 (bruger dine CSV-tal eller fallback).")
scol1, scol2, scol3 = st.columns(3)
with scol1:
    sim_ryger = st.selectbox("Ryger (simuleret)", ["Nej","Ja"], index=(1 if ryger=="Ja" else 0))
with scol2:
    sim_tc = st.number_input("Total-kolesterol (simuleret)", 2.0, 12.0, max(2.0, float(tc)-0.8), step=0.1, format="%.1f")
with scol3:
    sim_sbp = st.number_input("SBP (simuleret)", 80.0, 250.0, max(80.0, float(sbp)-20), step=1.0, format="%.0f")

sim_val = calculate_score2(int(alder), koen, float(sim_sbp), float(sim_tc), float(hdl), sim_ryger)
delta_text = None
if score2_final is not None and sim_val is not None:
    d = sim_val - score2_final
    delta_text = ("↘" if d < 0 else ("↗" if d > 0 else "→")) + f" {d:+.1f} %-point"
st.metric("SCORE2 efter simulering", f"{sim_val:.1f}%" if sim_val is not None else "—", delta=delta_text)

st.markdown("---")
st.caption("Denne app er en undervisningsprototype og erstatter ikke klinisk vurdering. Kontroller altid mod gældende danske retningslinjer.")
