import streamlit as st
import pandas as pd
from typing import Optional
from gp_htn_support import Patient, score2_intervention_flag, med_recommendations

st.set_page_config(page_title="Hypertension (Demo) — GP", page_icon="🩺", layout="wide")

st.title("🩺 Hypertension beslutningsstøtte (undervisnings-demo)")
st.caption("**VIGTIGT:** Undervisningsværktøj. Kræver klinisk vurdering og kontrol mod gældende danske retningslinjer (DSAM/SST/ESC).")

with st.expander("Om denne app"):
    st.markdown(
        """
        **Formål:** Illustrere, hvordan man kan omsætte retningslinjer til et simpelt beslutningsstøtte-værktøj i almen praksis.  
        **SCORE2:** Du kan enten indtaste SCORE2-% manuelt, **eller** uploade en DSAM-matrix som CSV til opslag, **eller** (senere) bruge den eksakte formel når koefficienter er indlagt.
        """
    )

st.header("1) Patientoplysninger")

colA, colB, colC = st.columns(3)
with colA:
    age = st.number_input("Alder (år)", min_value=18, max_value=100, value=58, step=1)
    sex = st.selectbox("Køn", ["F", "M"], index=1)
    sbp = st.number_input("Systolisk BT (mmHg)", min_value=80, max_value=280, value=150, step=1)
with colB:
    smoker = st.selectbox("Ryger?", ["Nej", "Ja"], index=0) == "Ja"
    ldl = st.number_input("LDL (mmol/L) — valgfri", min_value=0.0, max_value=15.0, value=3.0, step=0.1, format="%.1f")
with colC:
    st.write("**Comorbiditeter/forhold**")
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

st.header("2) Væsketal og elektrolytter (valgfrit)")
col1, col2, col3, col4 = st.columns(4)
with col1:
    na = st.number_input("Na+ (mmol/L)", min_value=100.0, max_value=170.0, value=138.0, step=0.1, format="%.1f")
with col2:
    k = st.number_input("K+ (mmol/L)", min_value=2.0, max_value=7.0, value=4.2, step=0.1, format="%.1f")
with col3:
    egfr = st.number_input("eGFR (mL/min/1.73m²)", min_value=5.0, max_value=200.0, value=85.0, step=1.0, format="%.0f")
with col4:
    urate = st.number_input("Urat (mmol/L)", min_value=0.0, max_value=2.0, value=0.35, step=0.01, format="%.2f")

st.header("3) SCORE2 — vælg metode")
mode = st.radio(
    "Metode til SCORE2",
    ["A) Indtast SCORE2-% manuelt", "B) Opslag i uploadet DSAM-matrix (CSV)", "C) Eksakt formel (kommer senere)"],
    index=0,
)

score2_pct: Optional[float] = None
note_text = ""

if mode.startswith("A"):
    score2_pct = st.number_input("SCORE2 % (tal aflæst fra DSAM/ESC-tabellen)", min_value=0.0, max_value=100.0, value=7.0, step=0.1, format="%.1f")
    note_text = "Manuel indtastning af % aflæst fra DSAM/ESC-skema."

elif mode.startswith("B"):
    st.info("Upload en CSV med kolonner (eksempel): age_band,sex,smoker,ldl_band,sbp_band,score2_pct")
    csv = st.file_uploader("Upload DSAM-matrix som CSV", type=["csv"])
    if csv is not None:
        try:
            df = pd.read_csv(csv)
            # Simple nearest-band match (requires your CSV to define band labels that match choices below)
            # For demo, we create selectboxes for band labels:
            cols = {"age_band","sex","smoker","ldl_band","sbp_band","score2_pct"}
            if not cols.issubset(df.columns.map(str).str.lower().tolist()):
                st.error("CSV mangler en eller flere kolonner: age_band, sex, smoker, ldl_band, sbp_band, score2_pct")
            else:
                # Access with case-insensitive columns
                df.columns = [c.lower() for c in df.columns]
                age_band = st.selectbox("Aldersbånd (fx 40-44, 45-49, ...)", sorted(df["age_band"].dropna().unique()))
                sex_band = st.selectbox("Køn", sorted(df["sex"].dropna().unique()))
                smoker_band = st.selectbox("Ryger", sorted(df["smoker"].dropna().unique()))
                ldl_band = st.selectbox("LDL-bånd", sorted(df["ldl_band"].dropna().unique()))
                sbp_band = st.selectbox("SBP-bånd", sorted(df["sbp_band"].dropna().unique()))
                m = df[(df["age_band"]==age_band) & (df["sex"]==sex_band) & (df["smoker"]==smoker_band)
                       & (df["ldl_band"]==ldl_band) & (df["sbp_band"]==sbp_band)]
                if len(m)==1:
                    score2_pct = float(m["score2_pct"].iloc[0])
                    st.success(f"Opslået SCORE2: {score2_pct:.1f}%")
                    note_text = "Fra uploadet DSAM-matrix (CSV)."
                elif len(m) > 1:
                    st.warning("Flere rækker matcher valget i CSV. Gør båndene mere specifikke.")
                else:
                    st.warning("Ingen match i CSV. Tjek bånd/labels.")
        except Exception as e:
            st.error(f"Kunne ikke læse CSV: {e}")
    else:
        st.warning("Upload CSV for at aktivere opslag.")

elif mode.startswith("C"):
    st.warning("Den eksakte SCORE2-formel indsættes her, når koefficienter er tilgængelige (ESC 2021).")
    st.write("**Plan:** Brug ESC's risikligninger (SCORE2 og SCORE2-OP) med aldersafhængige baseline hazards og kalibrering for Nordeuropa.")

# Saml patientobjekt
p = Patient(
    age=int(age),
    sex=sex,
    sbp=int(sbp),
    score2_pct=score2_pct,
    smoker=smoker,
    na=na if na>0 else None,
    k=k if k>0 else None,
    egfr=egfr if egfr>0 else None,
    urate=urate if urate>0 else None,
    diabetes=diabetes,
    ckd=ckd,
    cad=cad,
    heart_failure=heart_failure,
    af=af,
    stroke_tia=stroke_tia,
    pregnancy=pregnancy,
    gout=gout,
    asthma_copd=asthma_copd,
    peripheral_edema_tendency=edema,
    proteinuria=proteinuria,
)

st.header("4) Resultater")

colL, colR = st.columns(2)
with colL:
    st.subheader("SCORE2 og interventionsgrænse")
    s2 = score2_intervention_flag(p)
    thres = s2.get("threshold") if isinstance(s2, dict) else None
    over = s2.get("intervention_recommended") if isinstance(s2, dict) else None
    note = s2.get("note") if isinstance(s2, dict) else ""
    st.metric("Interventionsgrænse (alder)", thres if thres else "—")
    st.metric("Over grænsen?", over if over else "—")
    if note_text:
        st.caption(f"{note}  \n{note_text}")
    else:
        st.caption(note)

with colR:
    st.subheader("Medicinforslag (klasser)")
    out = med_recommendations(p)
    st.markdown("**Førstevalg (klasser):**")
    for x in out.get("first_line_options", []):
        st.write(f"- {x}")
    st.markdown("**Kombinationer (eksempler):**")
    for x in out.get("combinations", []):
        st.write(f"- {x}")
    st.markdown("**Undgå/forsigtighed:**")
    avoid_list = out.get("avoid_or_caution", [])
    if avoid_list:
        for x in avoid_list:
            st.write(f"- {x}")
    else:
        st.write("- (ingen specifikke)")

st.subheader("Rationaler (kort)")
for x in out.get("rationales", []):
    st.write(f"- {x}")

st.divider()
st.caption("Denne app er ikke et medicinsk produkt. Brug altid klinisk vurdering og verificér mod gældende danske retningslinjer.")
