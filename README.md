# Hypertension Decision Support (Streamlit)

**Teaching prototype** for GP use. Not a medical device. Verify all outputs against current Danish guidelines (DSAM/SST/ESC).

## One‑click deploy on Streamlit Community Cloud
1) Go to https://share.streamlit.io and sign in (GitHub/Google).
2) Click **'Upload a file'** (or **'New app' → 'From files'**) and upload these files:
   - `app.py`
   - `gp_htn_support.py`
   - `requirements.txt`
   - (optional) `DSAM_matrix_template.csv` if you want lookup mode (B).
3) Press **Deploy**. Wait ~1–2 minutes.
4) You get a public URL you can open on your phone and share with colleagues.

## Local run (optional)
```bash
pip install -r requirements.txt
streamlit run app.py
```
Then open the Network URL printed in the terminal on your phone (same Wi‑Fi).

## SCORE2 modes supported
- **A) Manual % input**: Type the SCORE2 percentage read from the DSAM/ESC table.
- **B) CSV lookup**: Upload a CSV with bands → percentage mapping (see `DSAM_matrix_template.csv`).
- **C) Exact formula (coming)**: Placeholder to implement ESC 2021 equations for SCORE2/SCORE2‑OP once coefficients are included.

## CSV schema
The CSV must contain columns:
`age_band,sex,smoker,ldl_band,sbp_band,score2_pct`
Each row is a unique combination that returns a SCORE2 %.
