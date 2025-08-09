# Hypertension & SCORE2 – Lægerne i Lind

Denne app er en undervisningsprototype til brug i almen praksis for vurdering af hypertensionpatienter.

## Funktioner
- SCORE2-beregning (ESC 2021) baseret på CSV-koefficienter
- Advarsler ved elektrolytforstyrrelser og nedsat nyrefunktion
- Check for kontraindikationer og lægemiddelinteraktioner
- Plan B-forslag ved kontraindikationer
- Diabetes-advarselsboks, da SCORE2 ikke er valideret for diabetikere
- Mulighed for at indlæse eksempelpatienter fra `example_patients.csv`

## Installation
1. Placer `app.py`, `score2_coefficients.csv`, `score2_baseline.csv` og `example_patients.csv` i samme mappe.
2. Installer afhængigheder:
   ```bash
   pip install streamlit pandas numpy
   ```
3. Kør appen:
   ```bash
   streamlit run app.py
   ```

## Kilder
- [ESC SCORE2 2021](https://academic.oup.com/eurheartj/article/42/25/2439/6297709)
- [Lægehåndbogen – Hypertension](https://www.sundhed.dk/sundhedsfaglig/laegehaandbogen/hjerte-kar/tilstande-og-sygdomme/blodtryk/hypertension/)
- [DSAM – Hypertension](https://www.dsam.dk)
