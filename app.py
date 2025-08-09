import math
from typing import Dict, Optional, Tuple, List
import streamlit as st
import pandas as pd

# =========================
# APP CONFIG
# =========================
st.set_page_config(
    page_title="Lægerne i Lind – Hypertension beslutningsstøtte",
    page_icon="🩺",
    layout="wide",
)

# =========================
# SIDEBAR: Forkortelser + links + eksempler
# =========================
with st.sidebar:
    st.markdown("## 🩺 Lægerne i Lind")
    st.markdown("**Hypertension beslutningsstøtte (undervisning)**")

    st.markdown("### 🔍 Forkortelser")
    st.write("**ACE-hæmmer** = Angiotensin Converting Enzyme-hæmmer")
    st.write("**ARB** = Angiotensin II receptorblokker")
    st.write("**CCB** = Calciumkanalblokker (DHP = dihydropyridin, fx amlodipin)")
    st.write("**MRA** = Mineralokortikoid-receptorantagonist (fx spironolakton)")
    st.write("**RAAS** = Renin–Angiotensin–Aldosteron-System")
    st.write("**CKD** = Kronisk nyresygdom")
    st.write("**AF** = Atrieflimren")

    st.markdown("---")
    st.markdown("### 🔗 Opslag")
    st.write("• cardio.dk – Hypertension (behandlingsprincipper)")
    st.write("• pro.medicin.dk – præparatdata (doser/kontraindikationer)")
    st.write("• Lægehåndbogen – diagnostik/livsstil/monitorering")

    st.markdown("---")
    st.subheader("📄 Eksempler")
    if st.button("Indlæs example_patients.csv"):
        try:
            df_ex = pd.read_csv("example_patients.csv")
            st.session_state["examples"] = df_ex.to_dict(orient="records")
            st.success(f"Indlæst {len(df_ex)} eksempler.")
        except Exception as e:
            st.error(f"Kunne ikke indlæse eksempler: {e}")

# =========================
# DATA (SCORE2 CSV’er – cache)
# =========================
@st.cache_data
def load_csv_or_none(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return None

coeff_df = load_csv_or_none("score2_coefficients.csv")
baseline_df = load_csv_or_none("score2_baseline.csv")

# Fallback værdier hvis CSV ikke findes (så appen altid virker)
COEFFS_FALLBACK = pd.DataFrame({
    "sex": ["M","M","M","M","M","M","M","M","M",
            "F","F","F","F","F","F","F","F","F"],
    "term": ["cage","csbp","ctc","chdl","smoke","cage*csbp","cage*ctc","cage*chdl","cage*smoke",
             "cage","csbp","ctc","chdl","smoke","cage*csbp","cage*ctc","cage*chdl","cage*smoke"],
    "coef": [0.3742,0.2777,0.1458,-0.2698,0.6012,-0.0255,-0.0281,0.0426,-0.0755,
             0.4648,0.3131,0.1002,-0.2606,0.7744,-0.0277,-0.0226,0.0613,-0.1088]
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

# =========================
# Hjælpefunktioner
# =========================
def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def age_adjusted_refs(age: int) -> Dict[str, Tuple[float, float]]:
    # Pædagogisk, enkel aldersjustering
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
    if val is None:
        return False
    lo, hi = ref
    return val < lo or val > hi

# =========================
# SCORE2 beregning (CSV-drevet)
# =========================
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
    try:
        risk_uncal = 1.0 - math.exp(math.log(s0) * math.exp(lp))
        risk_uncal = clamp(risk_uncal, 1e-9, 0.999999)
        ln_negln = math.log(-math.log(1.0 - risk_uncal))
        risk_cal = 1.0 - math.exp(-math.exp(scale1 + scale2 * ln_negln))
        return float(100.0 * clamp(risk_cal, 0.0, 0.9999))
    except Exception:
        return None

def risk_category(score2_pct: Optional[float], age: int) -> Tuple[str, str]:
    if score2_pct is None:
        return "Ukendt", "gray"
    r = score2_pct
    if 40 <= age <= 49:
        cuts = (2.5, 7.5)
    elif 50 <= age <= 59:
        cuts = (5.0, 10.0)
    elif 60 <= age <= 69:
        cuts = (7.5, 15.0)
    else:
        cuts = (10.0, 20.0)
    low, high = cuts
    if r < low:
        return "Lav risiko", "green"
    elif r < high:
        return "Moderat risiko", "orange"
    else:
        return "Høj/Meget høj risiko", "red"

# =========================
# INTERAKTIONER (andre præparater)
# =========================
INTERACTION_DEFS = {
    "Lithium": {"avoid": ["ACE-hæmmer","ARB","Tiazid(-lign.) diuretikum"], "why": "Øget lithium-niveau og toksicitet."},
    "NSAID (fast)": {"avoid": ["ACE/ARB + diuretikum (kombination)"], "why": "Øget risiko for AKI ('triple whammy')."},
    "Verapamil/diltiazem": {"avoid": ["Beta-blokker"], "why": "Risiko for AV-blok/bradykardi i kombination."},
    "Kaliumtilskud/K+-spare": {"avoid": ["MRA (spironolakton/eplerenon)","ACE-hæmmer","ARB"], "why": "Hyperkaliæmi-risiko."},
    "Prednisolon (høj dosis)": {"caution": ["Diuretika"], "why": "Væskeretention; kan modvirke antihypertensiv effekt."},
}

# =========================
# UI: Patientoplysninger
# =========================
st.title("🩺 Hypertension beslutningsstøtte — Lægerne i Lind (Demo)")
st.caption("Prototype til undervisning. Verificér altid mod gældende danske retningslinjer (cardio.dk / pro.medicin.dk / Lægehåndbogen).")
st.markdown("---")

example = None
if "examples" in st.session_state and st.session_state["examples"]:
    names = [r.get("navn","Case") for r in st.session_state["examples"]]
    choice = st.sidebar.selectbox("Vælg eksempel", ["(Ingen)"] + names)
    if choice != "(Ingen)":
        example = next(r for r in st.session_state["examples"] if r.get("navn","Case")==choice)

st.header("1) Patientoplysninger")
colA, colB, colC = st.columns(3)
with colA:
    alder = st.number_input("Alder (år)", 18, 95, int(example["alder"]) if example else 58)
    koen = st.selectbox("Køn", ["Mand","Kvinde"], index=(0 if not example else (0 if example.get("køn","Mand")=="Mand" else 1)))
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

# =========================
# Labs
# =========================
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
if outside(refs["na"], na):
    alerts.append("Na⁺ uden for reference — undgå tiazider ved hyponatriæmi.")
if outside(refs["k"], k):
    alerts.append("K⁺ uden for reference — RAAS/MRA kan give hyperkaliæmi.")
if egfr < refs["egfr"][0]:
    alerts.append("eGFR under reference — tiazider mindre effektive ved eGFR <30; forsigtighed med MRA.")
if outside(refs["urate"], urate):
    alerts.append("Urat forhøjet — tiazider kan forværre urinsyregigt.")
if alerts:
    st.warning("**Elektrolyt/nyrefunktion — opmærksomhedspunkter:**\n\n- " + "\n- ".join(alerts))

# =========================
# SCORE2
# =========================
st.header("3) SCORE2 (10-års risiko)")
colL, colR = st.columns([2,1])
with colL:
    st.caption("Beregnes automatisk ud fra CSV; fallback indbygget.")
with colR:
    manual_score2 = st.number_input("Manuel SCORE2 % (fallback)", 0.0, 100.0, 7.0, step=0.1)

auto_score2 = calculate_score2(int(alder), koen, float(sbp), float(tc), float(hdl), ryger)
score2_final = auto_score2 if auto_score2 is not None else manual_score2
cat, color = risk_category(score2_final, int(alder))
rc1, rc2 = st.columns([1,3])
with rc1:
    st.metric("SCORE2", f"{score2_final:.1f}%")
with rc2:
    ridx = {"green":"🟢","orange":"🟠","red":"🔴","gray":"⚪"}.get(color,"🟢")
    st.markdown(f"### {ridx} {cat}")

if diabetes:
    st.warning(
        "**Bemærk: SCORE2 er ikke tiltænkt personer med diabetes.**\n\n"
        "- Diabetes indebærer høj/meget høj kardiovaskulær risiko, som SCORE2 ikke afspejler korrekt.\n"
        "- Brug diabetes-specifik vurdering og følg højrisko-behandlingsmål."
    )

# =========================
# Interaktioner (andre præparater)
# =========================
st.header("4) Andre samtidige præparater — interaktionstjek")
st.caption("Marker hvis patienten får følgende (kan påvirke valg af BT-behandling).")
icol1, icol2, icol3 = st.columns(3)
interaction_state = {}
for i, drug in enumerate(INTERACTION_DEFS.keys()):
    with [icol1, icol2, icol3][i % 3]:
        interaction_state[drug] = st.checkbox(drug, value=False)

# =========================
# Indikation for behandling (konservativ vs farmakologisk) & forslag
# =========================

# Doser/handelsnavne (typiske DK-startdoser; check altid pro.medicin.dk ved ordination)
DRUGS = {
    "ACE": [
        {"name": "Perindopril (Coversyl®)", "dose": "2 mg x 1"},
        {"name": "Ramipril (Tritace®)", "dose": "2,5 mg x 1"},
    ],
    "ARB": [
        {"name": "Candesartan (Atacand®)", "dose": "8 mg x 1"},
        {"name": "Losartan (Cozaar®)", "dose": "50 mg x 1"},
    ],
    "CCB_DHP": [
        {"name": "Amlodipin (Norvasc®)", "dose": "5 mg x 1"},
    ],
    "THIAZIDE_LIKE": [
        {"name": "Indapamid (Natrilix SR®)", "dose": "1,5 mg x 1"},
        {"name": "Chlortalidon (Chlortalidon®)", "dose": "12,5 mg x 1"},
    ],
    "BETA": [
        {"name": "Metoprolol dep. (Selo-Zok®)", "dose": "25–50 mg x 1"},
    ],
    "MRA": [
        {"name": "Spironolakton (Spiron®)", "dose": "25 mg x 1"},
    ],
    "PREG": [
        {"name": "Labetalol (Trandate®)", "dose": "100–200 mg x 2"},
        {"name": "Nifedipin dep. (Adalat®/Nifedipin®)", "dose": "30 mg x 1"},
        {"name": "Methyldopa (Aldomet®)", "dose": "250 mg x 2–3"},
    ],
}

def has_hyperkalemia(k_val: float) -> bool:
    return k_val is not None and k_val >= 5.0

def has_hyponatremia(na_val: float) -> bool:
    return na_val is not None and na_val < 133.0

def egfr_low(egfr_val: float) -> bool:
    return egfr_val is not None and egfr_val < 30.0

def gout_risk(urate_val: float, gout_flag: bool) -> bool:
    return gout_flag or (urate_val is not None and urate_val > 0.42)

def sbp_grade(sbp_val: float) -> str:
    if sbp_val >= 180:
        return "Grad 3"
    elif sbp_val >= 160:
        return "Grad 2"
    elif sbp_val >= 140:
        return "Grad 1"
    elif sbp_val >= 130:
        return "Højt-normal"
    else:
        return "Normal"

def indication_for_treatment(sbp_val: float, score2_pct: float, high_risk_flags: bool) -> Tuple[str, str]:
    """
    Returnerer ('Conservative'/'Pharmacologic', begrundelse)
    Regler (for overskuelighed – pædagogisk):
      - SBP >=160: farmakologisk
      - SBP 140–159: farmakologisk hvis diabetes/CKD/moderat-høj SCORE2; ellers konservativ førstelinje
      - SBP 130–139: konservativ (med tæt opfølgning), farmakologisk hvis højrisiko (fx SCORE2 høj eller CKD/DM)
    """
    grade = sbp_grade(sbp_val)
    if grade in ("Grad 2", "Grad 3"):
        return "Pharmacologic", f"{grade}: behandlingsindikation."
    if grade == "Grad 1":
        if high_risk_flags or score2_pct >= 7.5:  # tærskel justeret m. risiko (pædagogisk)
            return "Pharmacologic", "Grad 1 + forhøjet risiko/komorbiditet: behandlingsindikation."
        else:
            return "Conservative", "Grad 1 uden højrisiko: start livsstilsintervention og tæt kontrol."
    if grade == "Højt-normal":
        if high_risk_flags or score2_pct >= 10.0:
            return "Pharmacologic", "Højt-normal + høj risiko/komorbiditet: kan overveje farmakologisk."
        else:
            return "Conservative", "Højt-normal: livsstilsintervention og revurdering."
    return "Conservative", "Normalt BT: livsstilsråd og observation."

def build_recommendation(
    sbp_val: float,
    diabetes_flag: bool,
    ckd_flag: bool,
    proteinuria_flag: bool,
    cad_flag: bool,
    heart_failure_flag: bool,
    af_flag: bool,
    pregnancy_flag: bool,
    edema_flag: bool,
    asthma_copd_flag: bool,
    gout_flag: bool,
    na_val: float, k_val: float, egfr_val: float, urate_val: float,
    score2_pct: float,
    interactions_checked: Dict[str, bool],
) -> Dict[str, List[Dict[str, str]]]:
    """
    Returnerer dict med nøgler:
      - 'conservative': liste af råd (dict med 'text')
      - 'firstline': liste af lægemidler (dict m. 'name','dose','note')
      - 'avoid': liste af advarsler (dict m. 'text')
      - 'rationale': liste af begrundelser (dict m. 'text')
      - 'planb': alternative forslag ved kontraindikation
    """
    out = {"conservative": [], "firstline": [], "avoid": [], "rationale": [], "planb": []}
    grade = sbp_grade(sbp_val)

    # ---- Risiko/komorbiditeter -> high_risk_flags
    high_risk_flags = any([diabetes_flag, ckd_flag, proteinuria_flag, heart_failure_flag, cad_flag, af_flag])
    mode, why = indication_for_treatment(sbp_val, score2_pct, high_risk_flags)
    out["rationale"].append({"text": f"BT-grad: {grade}. {why}"})

    # ---- Interaktioner (andre præparater)
    for drug, on in interactions_checked.items():
        if not on:
            continue
        entry = INTERACTION_DEFS.get(drug, {})
        why_i = entry.get("why")
        if "avoid" in entry:
            out["avoid"].append({"text": f"Interaktion ({drug}): undgå {', '.join(entry['avoid'])}."})
        if "caution" in entry:
            out["avoid"].append({"text": f"Interaktion ({drug}): forsigtighed med {', '.join(entry['caution'])}."})
        if why_i:
            out["rationale"].append({"text": f"Interaktion ({drug}): {why_i}"})

    # ---- Labs/kliniske flags -> kontraindikationer
    if has_hyperkalemia(k_val):
        out["avoid"].append({"text": "Hyperkaliæmi: undgå ACE/ARB/MRA indtil korrigeret."})
    if has_hyponatremia(na_val):
        out["avoid"].append({"text": "Hyponatriæmi: undgå tiazid-lignende diuretika."})
    if egfr_low(egfr_val):
        out["avoid"].append({"text": "eGFR <30: tiazid-lignende ineffektiv; MRA med forsigtighed (overvej loop-diuretikum ved volumenoverload)."})
    if gout_risk(urate_val, gout_flag):
        out["avoid"].append({"text": "Urinsyregigt/forhøjet urat: undgå tiazid-lignende diuretika."})
    if pregnancy_flag:
        out["avoid"].append({"text": "Graviditet: undgå ACE/ARB/MRA."})

    # ---- Konservativ behandling (alltid vurderet)
    conservative_list = [
        "Saltreduktion (<5–6 g salt/dag) og kost med grønt/fisk.",
        "Vægttab ved BMI>25 (mål 5–10%).",
        "Alkoholreduktion (max 7/14 genstande pr. uge Kv/M).",
        "Motion ≥150 min/uge (moderat) + styrke 2×/uge.",
        "Rygestop og stressreduktion/søvnoptimering.",
        "Hjemme-BT-kontrol og revurdering om 3–6 mdr.",
    ]
    for t in conservative_list:
        out["conservative"].append({"text": t})

    # ---- Farmakologiske forslag (valg afhænger af kontraindikationer/profil)
    def allowed_raas():
        return not (has_hyperkalemia(k_val) or pregnancy_flag)

    def allowed_thiazide():
        return not (has_hyponatremia(na_val) or egfr_low(egfr_val) or gout_risk(urate_val, gout_flag))

    def allowed_ccb_dhp():
        return True  # obs ødemer (note)
    # Basis-rasionale
    if ckd_flag or proteinuria_flag or diabetes_flag:
        out["rationale"].append({"text": "CKD/albuminuri/diabetes: RAAS-blokade anbefales som grundstamme."})
    if heart_failure_flag:
        out["rationale"].append({"text": "Hjertesvigt: ACE/ARB + betablokker ± MRA (HFrEF) – følg HF-vejledning."})
    if edema_flag:
        out["rationale"].append({"text": "DHP-CCB kan give ankelødem; kombiner evt. med ACE/ARB."})

    # Hovedvalg
    if mode == "Conservative":
        # Kun konservativ anbefaling som primær; men vis også 'kan overvejes' ved særlige profiler
        out["rationale"].append({"text": "Primært konservativ behandling valgt ud fra grad/risiko."})
        # Hvis særlige tilstande (fx CKD/diabetes) kan man dog overveje farmaka:
        if (diabetes_flag or ckd_flag or proteinuria_flag) and allowed_raas():
            for d in DRUGS["ACE"]:
                out["firstline"].append({"name": d["name"], "dose": d["dose"], "note": "Overvej ved CKD/albuminuri/diabetes."})
    else:
        # Farmakologisk: valg afhænger af grad/risiko og kontraindikationer
        need_combo = sbp_val >= 160 or (sbp_val >= 140 and (diabetes_flag or ckd_flag or proteinuria_flag or score2_pct >= 10.0))
        # RAAS som basis hvis muligt
        if allowed_raas():
            # ACE som 1. prioritet
            for d in DRUGS["ACE"]:
                out["firstline"].append({"name": d["name"], "dose": d["dose"], "note": "Basis."})
        else:
            # RAAS kontraindiceret -> CCB/thiazid først
            if allowed_ccb_dhp():
                for d in DRUGS["CCB_DHP"]:
                    out["firstline"].append({"name": d["name"], "dose": d["dose"], "note": "RAAS kontraindiceret."})
            if allowed_thiazide():
                for d in DRUGS["THIAZIDE_LIKE"]:
                    out["firstline"].append({"name": d["name"], "dose": d["dose"], "note": "RAAS kontraindiceret."})

        # Kombinationspartner(e)
        if need_combo:
            if allowed_ccb_dhp():
                for d in DRUGS["CCB_DHP"]:
                    out["firstline"].append({"name": d["name"], "dose": d["dose"], "note": "Kombinationsbehandling."})
            if allowed_thiazide():
                for d in DRUGS["THIAZIDE_LIKE"]:
                    out["firstline"].append({"name": d["name"], "dose": d["dose"], "note": "Kombinationsbehandling."})

        # Resistent (pædagogisk): overvej MRA hvis K+ tillader
        if sbp_val >= 160 and allowed_raas() and not has_hyperkalemia(k_val):
            for d in DRUGS["MRA"]:
                out["planb"].append({"text": f"Resistent HT: overvej {d['name']} {d['dose']} (monitorér K+/kreatinin)."})

        # Graviditet – erstat med sikre midler
        if pregnancy_flag:
            out["firstline"].clear()
            for d in DRUGS["PREG"]:
                out["firstline"].append({"name": d["name"], "dose": d["dose"], "note": "Graviditet – undgå RAAS/MRA."})

    # Astma/COPD note ved beta-blokkere
    if asthma_copd_flag:
        out["avoid"].append({"text": "Astma/COPD: undgå ikke-selektive beta-blokkere; overvej selektive ved indikation."})

    return out, mode, grade

# ====== Kør anbefalingsmotor ======
recommendation, mode, grade = build_recommendation(
    sbp_val=float(sbp),
    diabetes_flag=diabetes,
    ckd_flag=ckd,
    proteinuria_flag=proteinuria,
    cad_flag=cad,
    heart_failure_flag=heart_failure,
    af_flag=af,
    pregnancy_flag=pregnancy,
    edema_flag=edema,
    asthma_copd_flag=asthma_copd,
    gout_flag=gout,
    na_val=float(na),
    k_val=float(k),
    egfr_val=float(egfr),
    urate_val=float(urate),
    score2_pct=float(score2_final),
    interactions_checked=interaction_state
)

# =========================
# VISNING: Anbefalingskort
# =========================
st.header("5) Anbefaling")
card_col = st.container()
if mode == "Conservative":
    st.success("**Konservativ behandling anbefales** (grad/risiko taler for livsstilsintervention).")
else:
    st.warning("**Farmakologisk behandling anbefales** (grad/risiko taler for opstart).")

# Førstevalg (lægemidler)
st.subheader("Førstevalg (stof + handelsnavn + startdosis)")
if recommendation["firstline"]:
    for d in recommendation["firstline"]:
        note = f" — {d['note']}" if d.get("note") else ""
        st.write(f"- **{d['name']}** — {d['dose']}{note}")
else:
    st.write("- (Ingen specifikke førstevalg – se konservativ behandling/plan nedenfor.)")

# Konservativ behandling (vises altid)
st.subheader("Konservativ behandling (livsstilsråd)")
for r in recommendation["conservative"]:
    st.write(f"- {r['text']}")

# Undgå/forsigtighed
st.subheader("Undgå / forsigtighed")
if recommendation["avoid"]:
    for a in recommendation["avoid"]:
        st.error(f"- {a['text']}")
else:
    st.write("- (Ingen specifikke)")

# Plan B
st.subheader("Plan B (hvis utilstrækkelig effekt/kontraindikation)")
if recommendation["planb"]:
    for p in recommendation["planb"]:
        st.warning(f"- {p['text']}")
else:
    st.write("- (Ingen)")

# Begrundelser
st.subheader("Begrundelser (kort)")
for r in recommendation["rationale"]:
    st.write(f"- {r['text']}")

# =========================
# SIMULER ÆNDRING
# =========================
st.header("6) Simulér ændring (SCORE2)")
st.caption("Justér en parameter for at se forventet ændring i SCORE2 (anvender dine CSV-tal eller fallback).")
simc = st.columns(3)
with simc[0]:
    sim_ryger = st.selectbox("Ryger (simuleret)", ["Nej","Ja"], index=(1 if ryger=="Ja" else 0))
with simc[1]:
    sim_tc = st.number_input("Total-kolesterol (simuleret)", 2.0, 12.0, max(2.0, float(tc)-0.8), step=0.1, format="%.1f")
with simc[2]:
    sim_sbp = st.number_input("SBP (simuleret)", 80.0, 250.0, max(80.0, float(sbp)-20), step=1.0, format="%.0f")

sim_val = calculate_score2(int(alder), koen, float(sim_sbp), float(sim_tc), float(hdl), sim_ryger)
delta_text = None
if score2_final is not None and sim_val is not None:
    d = sim_val - score2_final
    arrow = "↘" if d < 0 else ("↗" if d > 0 else "→")
    delta_text = f"{arrow} {d:+.1f} %-point"
st.metric("SCORE2 efter simulering", f"{sim_val:.1f}%" if sim_val is not None else "—", delta=delta_text)

st.markdown("---")
st.caption("Denne app er en undervisningsprototype og erstatter ikke klinisk vurdering. Kontroller altid mod gældende danske retningslinjer (cardio.dk / pro.medicin.dk / Lægehåndbogen).")
