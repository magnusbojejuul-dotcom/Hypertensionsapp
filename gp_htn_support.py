
"""
gp_htn_support.py — Prototype decision support for hypertension in Danish general practice.

DISCLAIMER (IMPORTANT):
- This is a teaching/demo prototype. It does NOT replace clinical judgment.
- It is NOT a medical device and has NOT been validated against DSAM/ESC algorithms.
- All outputs must be checked against current Danish guidelines before use in patient care.

Design notes:
- SCORE2: For now, you ENTER the % risk number that you have read from the official DSAM/ESC table.
  The app will only determine whether the risk crosses the age-specific intervention thresholds
  (40–59: ≥5%; 60–69: ≥7.5%; 70–75: ≥10%).
- Medication logic is rules-based from commonly accepted first-line classes and typical lab/AE constraints.
  You MUST verify against current DSAM/SST/ESC texts.

Author: Demo generated for teaching
"""

from dataclasses import dataclass
from typing import Optional, List, Dict

# ------------------ Data structures ------------------

@dataclass
class Patient:
    age: int
    sex: str  # 'F' or 'M' (not used by rules below but kept for future use)
    sbp: Optional[int] = None  # systolic blood pressure (mmHg)
    score2_pct: Optional[float] = None  # % as read from DSAM/ESC chart
    smoker: Optional[bool] = None

    # Labs
    na: Optional[float] = None
    k: Optional[float] = None
    egfr: Optional[float] = None  # mL/min/1.73m2
    creat: Optional[float] = None  # µmol/L (optional if eGFR given)
    urate: Optional[float] = None  # mmol/L (or µmol/L if you prefer; annotate consistently)

    # Comorbidities / flags
    diabetes: bool = False
    ckd: bool = False
    cad: bool = False  # coronary artery disease / ischemic heart disease
    heart_failure: bool = False
    af: bool = False  # atrial fibrillation
    stroke_tia: bool = False
    pregnancy: bool = False
    gout: bool = False
    asthma_copd: bool = False
    peripheral_edema_tendency: bool = False
    proteinuria: bool = False  # significant albuminuria/proteinuria

# ------------------ SCORE2 handling ------------------

def intervention_threshold(age: int) -> float:
    if 40 <= age <= 59:
        return 5.0
    if 60 <= age <= 69:
        return 7.5
    if 70 <= age <= 75:
        return 10.0
    # Outside validated SCORE2 range for this threshold scheme
    return float('nan')

def score2_intervention_flag(p: Patient) -> Dict[str, Optional[str]]:
    th = intervention_threshold(p.age)
    if p.score2_pct is None or not (40 <= p.age <= 75):
        return {
            "threshold": None if th != th else f"{th:.1f}%",
            "intervention_recommended": None,
            "note": "Enter SCORE2 from DSAM/ESC chart to assess threshold crossing (valid ages 40–75)."
        }
    flag = p.score2_pct >= th
    return {
        "threshold": f"{th:.1f}%",
        "intervention_recommended": "Yes" if flag else "No",
        "note": "Threshold per DSAM: 40–59 ≥5%, 60–69 ≥7.5%, 70–75 ≥10%."
    }

# ------------------ Medication rules engine ------------------

def med_recommendations(p: Patient) -> Dict[str, List[str]]:
    """
    Returns a dict with keys:
      - 'first_line_options': list of class suggestions
      - 'combinations': list of combo suggestions
      - 'avoid_or_caution': list of warnings/avoidance items
      - 'rationales': list of short rationales
    """
    first_line = []
    combos = []
    avoid = []
    rationales = []

    # Baseline first-line classes often used in DK/ESC contexts:
    # Thiazide-like diuretic (indapamid or chlortalidon), ACE-hæmmer, ARB, dihydropyridin-CCB (amlodipin).
    # Beta-blokkere ved særlige indikationer (fx post-MI, angina, AF, migræne, tremor), ikke rutineførstevalg alene.

    # --- Lab- and comorbidity-driven adjustments ---

    # Potassium
    if p.k is not None:
        if p.k >= 5.0:
            avoid += ["ACE-hæmmer (midlertidigt/individuelt)", "ARB (midlertidigt/individuelt)", "K+-besparende diuretika (fx spironolakton)"]
            rationales += ["Hyperkaliæmi øger risiko ved ACE/ARB/K+-besparende; korrigér K+ og vurder årsag først."]
        elif p.k <= 3.4:
            # thiazides can worsen K+, so caution
            avoid += ["Tiazid(-lign.) diuretikum som monoterapi (overvej kombination med ACE/ARB eller K+-tilskud/kost)"]
            rationales += ["Hypokaliæmi kan forværres af tiazider; korrigér og/eller kombiner for at balancere K+."]

    # Sodium
    if p.na is not None and p.na <= 133:
        avoid += ["Tiazid(-lign.) diuretikum"]
        rationales += ["Hyponatriæmi kan forværres af tiazider; undgå tilstanden er korrigeret."]

    # eGFR/CKD
    if p.egfr is not None:
        if p.egfr < 30:
            avoid += ["Tiazid(-lign.) diuretikum (nedsat effekt ved eGFR <30)", "K+-besparende diuretika (forsigtighed)"]
            rationales += ["Tiazider er ofte ineffektive ved eGFR <30; overvej loop-diuretika ved volumenoverload."]
        if p.egfr < 60 or p.ckd or p.proteinuria:
            first_line += ["ACE-hæmmer eller ARB (nefroprotektion ved proteinuri/CKD)"]
            rationales += ["ACE/ARB reducerer albuminuri og beskytter nyrefunktion. Monitorér kreatinin/K+."]

    # Diabetes
    if p.diabetes:
        first_line += ["ACE-hæmmer eller ARB (især ved albuminuri)"]
        rationales += ["Ved diabetes og albuminuri anbefales RAAS-blokade som grundstamme."]

    # CAD/Stroke/Atherosclerotic CVD
    if p.cad or p.stroke_tia:
        first_line += ["ACE-hæmmer eller ARB", "DHP-CCB (amlodipin)"]
        rationales += ["Sekundærprofylakse: RAAS-blokade og/eller CCB har outcome-data; beta-blokker ved angina/post-MI."]

    # Heart failure
    if p.heart_failure:
        first_line += ["ACE-hæmmer eller ARB", "Beta-blokker (HF-udgave)", "Mineralokortikoid-antagonist (ved HFrEF og efter K+/nyrer)"]
        rationales += ["HFrEF: livsforlængende behandling. Vurder ejection fraction og guideline-specifik titrering."]

    # AF
    if p.af:
        first_line += ["Beta-blokker (hvis frekvenskontrol ønskes)"]
        rationales += ["AF: beta-blokker kan være hensigtsmæssig ved behov for frekvenskontrol."]

    # Gout/urate
    if p.gout or (p.urate is not None and p.urate > 0.42):  # mmol/L example threshold
        avoid += ["Tiazid(-lign.) diuretikum"]
        rationales += ["Tiazider kan øge urinsyre og trigge urinsyregigt."]

    # Asthma/COPD
    if p.asthma_copd:
        avoid += ["Ikke-selektive beta-blokkere"]
        rationales += ["Bronkokonstriktionsrisiko ved ikke-selektive beta-blokkere."]

    # Edema tendency
    if p.peripheral_edema_tendency:
        avoid += ["DHP-CCB som monoterapi (overvej kombination med ACE/ARB)"]
        rationales += ["Amlodipin kan give ankelsvulst; RAAS-kombination reducerer risiko."]

    # Pregnancy
    if p.pregnancy:
        avoid += ["ACE-hæmmer", "ARB", "MRA (spironolakton/eplerenon)"]
        first_line += ["Labetalol", "Nifedipin (retard)", "Methyldopa"]
        rationales += ["Graviditet: undgå RAAS-blokade. Foretræk labetalol, nifedipin (retard) eller methyldopa."]

    # Default first-line if none added yet
    if not first_line:
        first_line += ["ACE-hæmmer ELLER ARB", "DHP-CCB (amlodipin)", "Tiazid-lignende diuretikum (indapamid/klortalidon)"]

    # Combination suggestions (typiske, evidensbaserede)
    combos += [
        "ACE-hæmmer/ARB + DHP-CCB",
        "ACE-hæmmer/ARB + tiazid-lignende diuretikum",
        "DHP-CCB + tiazid-lignende diuretikum (hvis RAAS-blokade ikke tåles)"
    ]

    # Remove duplicates while preserving order
    def unique(seq):
        seen = set()
        out = []
        for x in seq:
            if x not in seen:
                out.append(x); seen.add(x)
        return out

    return {
        "first_line_options": unique(first_line),
        "combinations": unique(combos),
        "avoid_or_caution": unique(avoid),
        "rationales": unique(rationales),
    }

# ------------------ Simple CLI demo ------------------

def demo():
    print("=== Hypertension demo (teaching prototype) ===")
    age = int(input("Alder (år): "))
    sex = input("Køn [F/M]: ").upper().strip()
    sbp = int(input("Systolisk BT (mmHg): "))
    score2_str = input("SCORE2 % (indtast tallet aflæst fra DSAM/ESC-tabellen, fx 7): ").strip()
    score2 = float(score2_str) if score2_str else None

    # Labs (optional)
    na = input("Na+ (mmol/L) [tom hvis ukendt]: "); na = float(na) if na else None
    k  = input("K+ (mmol/L) [tom hvis ukendt]: "); k  = float(k) if k else None
    egfr = input("eGFR (mL/min/1.73m2) [tom hvis ukendt]: "); egfr = float(egfr) if egfr else None
    urate = input("Urat (mmol/L) [tom hvis ukendt]: "); urate = float(urate) if urate else None

    # Flags
    def yesno(q):
        ans = input(q + " [j/n]: ").lower().strip()
        return ans == 'j'

    flags = {
        "diabetes": yesno("Diabetes?"),
        "ckd": yesno("Kronisk nyresygdom (CKD)?"),
        "cad": yesno("Kendt iskæmisk hjertesygdom?"),
        "heart_failure": yesno("Hjertesvigt?"),
        "af": yesno("Atrieflimren?"),
        "stroke_tia": yesno("Tidligere apopleksi/TIA?"),
        "pregnancy": yesno("Gravid?"),
        "gout": yesno("Urin-syregigt?"),
        "asthma_copd": yesno("Astma/COPD?"),
        "peripheral_edema_tendency": yesno("Tendens til perifere ødemer?"),
        "proteinuria": yesno("Betydende albuminuri/proteinuri?"),
    }

    p = Patient(
        age=age, sex=sex, sbp=sbp, score2_pct=score2,
        na=na, k=k, egfr=egfr, urate=urate,
        **flags
    )

    print("\n--- SCORE2 og interventionsgrænse ---")
    s2 = score2_intervention_flag(p)
    print(f"Interventionsgrænse (alder): {s2['threshold']}")
    print(f"Over grænsen? {s2['intervention_recommended']}")
    print(f"Note: {s2['note']}")

    print("\n--- Medicinforslag (klasser) ---")
    out = med_recommendations(p)
    print("Førstevalg (klasser):")
    for x in out["first_line_options"]:
        print(" -", x)

    print("\nKombinationer (eksempler):")
    for x in out["combinations"]:
        print(" -", x)

    print("\nUndgå/forsigtighed:")
    if out["avoid_or_caution"]:
        for x in out["avoid_or_caution"]:
            print(" -", x)
    else:
        print(" - (ingen specifikke)")

    print("\nRationaler (kort):")
    for x in out["rationales"]:
        print(" -", x)

if __name__ == "__main__":
    demo()
