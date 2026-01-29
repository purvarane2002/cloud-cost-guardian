# Cloud Cost Guardian

AWS cost + carbon monitoring tool that scans cloud resources and highlights potential cost / CO₂ waste.

## What it does
- Scans EC2/EBS usage (via AWS APIs)
- Estimates cost and CO₂ impact
- Provides a Streamlit dashboard for insights

## Repo structure
- `dashboard/` — Streamlit app
- `lambda/` — scan + reporting scripts (Lambda-ready)
• dashboard/ — Streamlit app
• lambda/ — scan + reporting scripts (Lambda-ready)

## Run locally (dashboard)
```bash
cd dashboard
python -m pip install -r requirements.txt
streamlit run app.py

## Tech Stack
- Python
- Streamlit
- AWS (EC2, EBS, CloudWatch)
- Boto3

## Output
- Estimated AWS cost usage
- CO₂ impact metrics
- Interactive dashboard insights
