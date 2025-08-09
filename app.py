# app.py
# Hypertension beslutningsstøtte — Lægerne i Lind (Demo)
# Funktioner:
# - Automatisk SCORE2 (ESC 2021) med indbyggede koefficienter og LOW-risk (Nordeuropa) kalibrering
# - Mulighed for upload af CSV for at overskrive standardtallene
# - Diabetes-advarselsboks (SCORE2 ikke tiltænkt personer med diabetes)
# - Interaktions-/kontraindikationstjek (checkboxes)
# - Sidebar med forkortelser + DSAM/Lægehåndbogen-links
# - Alderskorrigerede elektrolytter (Na+, K+, eGFR, urat) m. normalområder + advarsler
# - Farvekodet risikoprofilkort
# - “Simulér ændring”

import math
from typing import Dict, Optional, Tuple, List
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Hypertension beslutningsstøtte — Lægerne i Lind", page_icon="🩺", layout="wide")

# ------------------------------- Hjælpefunktioner -------------------------------
def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def age_adjusted_refs(age: int) -> Dict[str, Tuple[float, float]]:
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
    lo, hi = ref; return val < lo or val > hi

# ------------------------------- SCORE2 (indbyggede tal) -------------------------------
# Log-SHR koefficienter (SCORE2, mænd/kvinder) for variabler og alder-interaktioner.
# Kilde: SCORE2 Updated Supplementary Material (tabel med "Log SHRs" og interaktioner).  
COEFFS_BUILTIN = {
    "M": {
        "cage": 0.3742, "csbp": 0.2777, "ctchol": 0.1458, "chdl": -0.2698, "current_smoker": 0.6012, "diabetes": 0.6457,
        "cage_csbp": -0.0255, "cage_ctchol": -0.0281, "cage_chdl": 0.0426, "cage_smoker": -0.0755, "cage_diabetes": -0.0983
    },
    "F": {
        "cage": 0.4648, "csbp": 0.3131, "ctchol": 0.1002, "chdl": -0.2606, "current_smoker": 0.7744, "diabetes": 0.8096,
        "cage_csbp": -0.0277, "cage_ctchol": -0.0226, "cage_chdl": 0.0613, "cage_smoker": -0.1088, "cage_diabetes": -0.1272
    }
}
# Baseline survival ved 10 år (S0) fra derivationskohorter.  
S0_10Y = {"M": 0.9605, "F": 0.9776}
# Recalibration scales (LOW-risk region ~ Nordeuropa).  
SCALES_LOW = {
    "M": {"scale1": -0.5699, "scale2": 0.7476},
    "F": {"scale1": -0.7380, "scale2": 0.7019},
}

# CSV skema der kan overskrive ovenstående:
# coeffs: sex,term,coef   (term ∈ {cage,csbp,ctchol,chdl,current_smoker,diabetes,cage_csbp,cage_ctchol,cage_chdl,cage_smoker,cage_diabetes})
# baseline: sex,region,s0_10y,scale1,scale2  (region kan være fx "Low" eller "NorthernEurope")
REQUIRED_TERMS = {"cage","csbp","ctchol","chdl","current_smoker","diabetes","cage_csbp","cage_ctchol","cage_chdl","cage_smoker","cage_diabetes"}

def load_coeffs_and_scales(coeffs_csv: Optional[pd.DataFrame], baseline_csv: Optional[pd.DataFrame]):
    coeffs = { "M": COEFFS_BUILTIN["M"].copy(), "F": COEFFS_BUILTIN["F"].copy() }
    s0 = S0_10Y.copy()
    scales = { "M": SCALES_LOW["M"].copy(), "F": SCALES_LOW["F"].copy() }
    if coeffs_csv is not None:
        df = coeffs_csv.copy(); df.columns = [c.lower() for c in df.columns]
        if all(c in df.columns for c in ["sex","term","coef"]):
            for sex in ["M","F"]:
                sub = df[df["sex"].str.upper().str[0]==sex]
                have = set(sub["term"].str.lower())
                if REQUIRED_TERMS.issubset(have):
                    coeffs[sex] = {t.lower(): float(sub[sub["term"].str.lower()==t]["coef"].iloc[0]) for t in REQUIRED_TERMS}
    if baseline_csv is not None:
        db = baseline_csv.copy(); db.columns = [c.lower() for c in db.columns]
        if all(c in db.columns for c in ["sex","region","s0_10y","scale1","scale2"]):
            for sex in ["M","F"]:
                cand = db[db["sex"].str.upper().str[0]==sex]
                # vælg "NorthernEurope" eller "Low" hvis tilgængelig
                pick = None
                if not cand.empty:
                    ne = cand[cand["region"].str.lower().isin(["northerneurope","low","low-risk","nordeuropa"])]
                    pick = ne.iloc[0] if len(ne)>0 else cand.iloc[0]
                if pick is not None:
                    s0[sex] = float(pick["s0_10y"])
                    scales[sex] = {"scale1": float(pick["scale1"]), "scale2": float(pick["scale2"])}
    return coeffs, s0, scales

def compute_score2(
    sex: str, age: float, sbp: float, tchol: float, hdl: float, smoker: bool, diabetes_flag: bool,
    coeffs_csv: Optional[pd.DataFrame]=None, baseline_csv: Optional[pd.DataFrame]=None
) -> Optional[float]:
    coeffs, s0_map, scales_map = load_coeffs_and_scales(coeffs_csv, baseline_csv)
    sex_key = sex.upper()[0]
    c = coeffs[sex_key]; s0 = s0_map[sex_key]; sc = scales_map[sex_key]
    # Transformationer (ESC):
    cage = (age - 60.0)/5.0
    csbp = (sbp - 120.0)/20.0
    ctchol = (tchol - 6.0)/1.0
    chdl = (hdl - 1.3)/0.5
    current_smoker = 1.0 if smoker else 0.0
    diabetes = 1.0 if diabetes_flag else 0.0  # sættes i praksis til 0 for målgruppen, men vi viser tallet med advarsel
    lp = (
        c["cage"]*cage + c["csbp"]*csbp + c["ctchol"]*ctchol + c["chdl"]*chdl +
        c["current_smoker"]*current_smoker + c["diabetes"]*diabetes +
        c["cage_csbp"]*cage*csbp + c["cage_ctchol"]*cage*ctchol + c["cage_chdl"]*cage*chdl +
        c["cage_smoker"]*cage*current_smoker + c["cage_diabetes"]*cage*diabetes
    )
    try:
        uncal = 1.0 - math.exp(math.log(s0) * math.exp(lp))
        uncal = clamp(uncal, 1e-8, 0.999999)
        ln_negln = math.log(-math.log(1.0 - uncal))
        cal = 1.0 - math.exp(-math.exp(sc["scale1"] + sc["scale2"] * ln_negln))
        return float(100.0 * clamp(cal, 0.0, 0.9999))
    except Exception:
        return None

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

# ------------------------------- Interaktioner/kontraindikation -------------------------------
INTERACTION_FLAGS = {
    "Lithium": {"avoid": ["ACE-hæmmer", "ARB", "Tiazid(-lign.) diuretikum"], "why": "Øget lithium-niveau og toksicitet."},
    "NSAID (fast)": {"avoid": ["ACE/ARB + diuretikum (kombination)"], "why": "Øget risiko for AKI ('triple whammy')."},
    "Verapamil/diltiazem": {"avoid": ["Beta-blokker"], "why": "Risiko for AV-blok/bradykardi i kombination."},
    "Kaliumtilskud/K+-spare": {"avoid": ["MRA (spironolakton/eplerenon)", "ACE-hæmmer", "ARB"], "why": "Hyperkaliæmi-risiko."},
    "Prednisolon (høj dosis)": {"caution": ["Diuretika"], "why": "Væskeretention; kan modvirke antihypertensiv effekt."},
}
GUIDELINE_LINKS = {
    "ACE-hæmmer": "https://www.sundhed.dk/",
    "ARB": "https://www.sundhed.dk/",
    "DHP-CCB (amlodipin)": "https://www.sundhed.dk/",
    "Tiazid-lignende diuretikum": "https://www.sundhed.dk/",
    "Beta-blokker": "https://www.sundhed.dk/",
    "MRA": "https://www.sundhed.dk/",
}

def med_engine(diabetes: bool, ckd: bool, proteinuria: bool, cad: bool, heart_failure: bool, af: bool,
               stroke_tia: bool, pregnancy: bool, asthma_copd: bool, edema: bool, gout: bool,
               na: Optional[float], k: Optional[float], egfr: Optional[float], urate: Optional[float],
               interactions_checked: Dict[str, bool]) -> Dict[str, List[str]]:
    first_line, combos, avoid, rationales = [], [], [], []
    first_line += ["ACE-hæmmer ELLER ARB", "DHP-CCB (amlodipin)", "Tiazid-lignende diuretikum (indapamid/klortalidon)"]
    combos += ["ACE/ARB + DHP-CCB", "ACE/ARB + Tiazid-lignende", "DHP-CCB + Tiazid-lignende (ved intolerance for ACE/ARB)"]
    if (ckd or proteinuria):
        first_line.insert(0, "ACE-hæmmer ELLER ARB (nefroprotektion ved albuminuri/CKD)")
        rationales += ["RAAS-blokade reducerer albuminuri og beskytter nyrefunktion."]
    if diabetes:
        first_line.insert(0, "ACE-hæmmer ELLER ARB (ved diabetes, især ved albuminuri)")
        rationales += ["Diabetes: RAAS-blokade er ofte grundstammen; monitorér K+/kreatinin."]
    if cad or stroke_tia:
        first_line += ["DHP-CCB (amlodipin)"]; rationales += ["Aterosklerose/sekundærprofylakse: RAAS/CCB har outcome-data."]
    if heart_failure:
        first_line.insert(0, "ACE/ARB + Beta-blokker (HF-udgave) ± MRA (HFrEF)"); rationales += ["HFrEF: livsforlængende; følg HF-retningslinjer."]
    if af:
        first_line += ["Beta-blokker (frekvenskontrol)"]; rationales += ["AF: beta-blokker ved frekvenskontrol."]
    if pregnancy:
        avoid += ["ACE-hæmmer","ARB","MRA"]; first_line = ["Labetalol","Nifedipin (retard)","Methyldopa"]; rationales += ["Graviditet: undgå RAAS-blokade."]
    if k is not None and k >= 5.0:
        avoid += ["ACE-hæmmer","ARB","MRA"]; rationales += ["Hyperkaliæmi: undgå RAAS/MRA indtil korrigeret."]
    if k is not None and k <= 3.4:
        rationales += ["Hypokaliæmi: tiazider kan forværre; korrigér/kombinér."]
    if na is not None and na < 133.0:
        avoid += ["Tiazid-lignende diuretikum"]; rationales += ["Hyponatriæmi: tiazider kan forværre."]
    if egfr is not None and egfr < 30.0:
        avoid += ["Tiazid-lignende diuretikum (ineffektiv <30)", "MRA (forsigtighed)"]; rationales += ["Ved eGFR<30: overvej loop-diuretikum."]
    if gout or (urate is not None and urate > 0.42):
        avoid += ["Tiazid-lignende diuretikum"]; rationales += ["Urinsyregigt: tiazider kan øge urinsyre."]
    if asthma_copd:
        avoid += ["Ikke-selektive beta-blokkere"]; rationales += ["Astma/COPD: bronkokonstriktionsrisiko."]
    if edema:
        rationales += ["Ankelødem ved DHP-CCB; mindskes ved kombination med ACE/ARB."]
    for drug, on in interactions_checked.items():
        if not on: continue
        entry = INTERACTION_FLAGS.get(drug, {})
        if "avoid" in entry: avoid += entry["avoid"]
        if "caution" in entry: avoid += entry["caution"]
        why = entry.get("why"); if why: rationales.append(f"Interaktion ({drug}): {why}")
    plan_b = []
    if any(x in avoid for x in ["ACE-hæmmer","ARB"]):
        plan_b += ["DHP-CCB + Tiazid-lignende", "Tilføj Beta-blokker ved indikation (angina/AF/HF)."]
    def uniq(seq):
        seen=set(); out=[]
        for x in seq:
            if x not in seen: out.append(x); seen.add(x)
        return out
    return {"first_line": uniq(first_line), "combos": uniq(combos), "avoid": uniq(avoid),
            "rationales": uniq(rationales), "plan_b": uniq(plan_b)}

# ------------------------------- Sidebar -------------------------------
with st.sidebar:
    st.header("Forkortelser")
    st.markdown("- **ACE-hæmmer**: Angiotensin Converting Enzyme-hæmmer  \n- **ARB**: Angiotensin II receptorblokker  \n- **CCB**: Calciumkanalblokker  \n- **DHP**: Dihydropyridin (type af CCB)  \n- **MRA**: Mineralokortikoid-receptorantagonist  \n- **RAAS**: Renin–Angiotensin–Aldosteron-System  \n- **AF**: Atrieflimren  \n- **CKD**: Kronisk nyresygdom")
    st.header("Opslag")
    st.markdown("- [DSAM — Hypertension](https://www.dsam.dk)  \n- [Lægehåndbogen](https://www.sundhed.dk)  \n- [ESC SCORE2 (EHJ 2021)](https://academic.oup.com/eurheartj/article/42/25/2439/6297709)")

# ------------------------------- Hoved-UI -------------------------------
st.title("🩺 Hypertension beslutningsstøtte — Lægerne i Lind (Demo)")
st.caption("Undervisningsprototype. Verificér altid mod gældende retningslinjer (DSAM/SST/ESC).")

st.header("1) Patientoplysninger")
colA, colB, colC = st.columns(3)
with colA:
    age = st.number_input("Alder (år)", min_value=18, max_value=95, value=58, step=1)
    sex = st.selectbox("Køn", ["F", "M"], index=1)
    smoker = st.selectbox("Ryger?", ["Nej", "Ja"], index=0) == "Ja"
with colB:
    sbp = st.number_input("Systolisk BT (mmHg)", min_value=80, max_value=250, value=150, step=1)
    tchol = st.number_input("Total-kolesterol (mmol/L)", min_value=2.0, max_value=12.0, value=5.8, step=0.1, format="%.1f")
with colC:
    hdl = st.number_input("HDL (mmol/L)", min_value=0.5, max_value=4.0, value=1.3, step=0.1, format="%.1f")
    st.write("**Komorbiditeter/forhold**")
    diabetes = st.checkbox("Diabetes", value=False)
    ckd = st.checkbox("CKD/kronisk nyresygdom", value=False)
    proteinuria = st.checkbox("Betydende albuminuri/proteinuri", value=False)
    cad = st.checkbox("Iskæmisk hjertesygdom", value=False)
    heart_failure = st.checkbox("Hjertesvigt", value=False)
    af = st.checkbox("Atrieflimren", value=False)
    stroke_tia = st.checkbox("Apopleksi/TIA", value=False)
    pregnancy = st.checkbox("Graviditet", value=False)
    gout = st.checkbox("Urin-syregigt", value=False)
    asthma_copd = st.checkbox("Astma/COPD", value=False)
    edema = st.checkbox("Tendens til perifere ødemer", value=False)

st.header("2) Væsketal/elektrolytter")
refs = age_adjusted_refs(int(age))
col1, col2, col3, col4 = st.columns(4)
with col1:
    na = st.number_input(f"Na⁺ (mmol/L) — ref {refs['na'][0]:.1f}–{refs['na'][1]:.1f}", min_value=110.0, max_value=170.0, value=138.0, step=0.1, format="%.1f")
with col2:
    k = st.number_input(f"K⁺ (mmol/L) — ref {refs['k'][0]:.1f}–{refs['k'][1]:.1f}", min_value=2.0, max_value=7.0, value=4.2, step=0.1, format="%.1f")
with col3:
    egfr = st.number_input(f"eGFR (mL/min/1.73m²) — ref {refs['egfr'][0]:.0f}–{refs['egfr'][1]:.0f}", min_value=5.0, max_value=200.0, value=85.0, step=1.0, format="%.0f")
with col4:
    urate = st.number_input(f"Urat (mmol/L) — ref {refs['urate'][0]:.2f}–{refs['urate'][1]:.2f}", min_value=0.05, max_value=2.0, value=0.35, step=0.01, format="%.2f")

alert_msgs=[]
if outside(refs["na"], na): alert_msgs.append("Na⁺ uden for reference — vurder årsag; undgå tiazider ved hyponatriæmi.")
if outside(refs["k"], k): alert_msgs.append("K⁺ uden for reference — årsag? RAAS/MRA kan give hyperkaliæmi.")
if egfr < refs["egfr"][0]: alert_msgs.append("eGFR under reference — tiazider mindre effektive ved eGFR<30; pas på RAAS/MRA.")
if outside(refs["urate"], urate): alert_msgs.append("Urat forhøjet — tiazider kan forværre urinsyregigt.")
if alert_msgs: st.warning("**Elektrolyt/nyrefunktion — opmærksomhedspunkter:**\n\n- " + "\n- ".join(alert_msgs))

st.header("3) SCORE2")
colS1, colS2 = st.columns([2,1])
with colS1:
    st.markdown("**(Valgfrit)** Upload CSV for at overskrive standardtallene")
    coeffs_file = st.file_uploader("score2_coefficients.csv (sex,term,coef)", type=["csv"], key="coeffs")
    base_file = st.file_uploader("score2_baseline.csv (sex,region,s0_10y,scale1,scale2)", type=["csv"], key="baseline")
with colS2:
    manual_score2 = st.number_input("Manuel SCORE2 % (fallback)", min_value=0.0, max_value=100.0, value=7.0, step=0.1, format="%.1f")

auto_score2 = compute_score2(sex, float(age), float(sbp), float(tchol), float(hdl), smoker, diabetes, 
                             pd.read_csv(coeffs_file) if coeffs_file else None,
                             pd.read_csv(base_file) if base_file else None)
score2_final = auto_score2 if auto_score2 is not None else manual_score2

st.subheader("Risikoprofil")
cat, color = risk_category(score2_final, int(age))
rc1, rc2 = st.columns([1,3])
with rc1: st.metric("SCORE2 (10 år)", f"{score2_final:.1f}%" if score2_final is not None else "—")
with rc2:
    ridx = {"green":"🟢","orange":"🟠","red":"🔴","gray":"⚪"}.get(color,"🟢")
    st.markdown(f"### {ridx} {cat}")

if diabetes:
    st.warning("**Bemærk: SCORE2 er ikke tiltænkt personer med diabetes.**\n\n"
               "- Diabetes medfører høj/ meget høj kardiovaskulær risiko, som SCORE2 ikke afspejler korrekt.\n"
               "- Brug diabetes-specifik vurdering og ESC-behandlingsmål for høj risiko.")

st.header("4) Nuværende medicin og interaktioner")
st.caption("Marker relevante præparater for at tjekke kontraindikationer/interaktioner.")
cols = st.columns(3); interaction_state={}
for i, drug in enumerate(list(INTERACTION_FLAGS.keys())):
    with cols[i%3]: interaction_state[drug]=st.checkbox(drug, value=False)

st.header("5) Forslag til behandling")
engine_out = med_engine(diabetes, ckd, proteinuria, cad, heart_failure, af, stroke_tia, pregnancy,
                        asthma_copd, edema, gout, na, k, egfr, urate, interaction_state)

cL, cR = st.columns(2)
with cL:
    st.subheader("Førstevalg (klasser)")
    for x in engine_out["first_line"]:
        link = GUIDELINE_LINKS.get(x.split(" (")[0], None)
        st.write(f"- {x}" + (f"  🔗 [{link}]({link})" if link else ""))
    st.markdown("**Kombinationer (eksempler):**")
    for x in engine_out["combos"]: st.write(f"- {x}")
with cR:
    st.subheader("Undgå / forsigtighed")
    if engine_out["avoid"]:
        for x in engine_out["avoid"]: st.write(f"- {x}")
    else: st.write("- (ingen specifikke)")
    st.subheader("Plan B (hvis nødvendigt)")
    if engine_out["plan_b"]:
        for x in engine_out["plan_b"]: st.write(f"- {x}")
    else: st.write("- (ingen)")

st.subheader("Begrundelser (kort)")
for x in engine_out["rationales"]: st.write(f"- {x}")

st.header("6) Simulér ændring")
st.caption("Juster en parameter og se ændring i SCORE2 (bruger de indbyggede tal eller dine CSV).")
simc = st.columns(3)
with simc[0]:
    sim_smoker = st.selectbox("Ryger (simuleret)", ["Nej","Ja"], index=0)=="Ja"
with simc[1]:
    sim_tchol = st.number_input("Total-kolesterol (simuleret)", min_value=2.0, max_value=12.0, value=max(2.0, tchol-0.8), step=0.1, format="%.1f")
with simc[2]:
    sim_sbp = st.number_input("SBP (simuleret)", min_value=80.0, max_value=250.0, value=max(80.0, sbp-20), step=1.0, format="%.0f")
sim_val = compute_score2(sex, float(age), float(sim_sbp), float(sim_tchol), float(hdl), sim_smoker, diabetes,
                         pd.read_csv(coeffs_file) if coeffs_file else None,
                         pd.read_csv(base_file) if base_file else None)
delta_text = None
if score2_final is not None and sim_val is not None:
    d = sim_val - score2_final
    delta_text = ("↘" if d<0 else ("↗" if d>0 else "→")) + f" {d:+.1f} %-point"
st.metric("SCORE2 efter simulering", f"{sim_val:.1f}%" if sim_val is not None else "—", delta=delta_text)
st.divider()
st.caption("Denne app er en undervisningsprototype og erstatter ikke klinisk vurdering. Kontroller altid mod gældende danske retningslinjer.")
