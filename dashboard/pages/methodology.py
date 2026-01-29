import streamlit as st

st.title("📚 Methodology")

st.markdown("""
## Scope
This dashboard measures the cost and CO₂ emissions of AWS EC2 instances and EBS volumes. It identifies when resources are underused and classifies this as waste.

---

## Waste Detection Rules

### EC2 Instances
- **Idle** → when both CPU < **5%** and Network < **5 KB/s** (24-h average)  
  → All hourly cost & CO₂ emissions are classified as **waste**.
- **Busy** → when CPU ≥ 5% **or** Network ≥ 5 KB/s  
  → Cost is productive, so **waste = $0** (CO₂ still tracked as total, not waste).

### EBS Volumes
- **Unattached volumes** → **100% waste** (they incur cost without usage).
- **Attached volumes** → considered active (not waste).

---

## Calculations

- **Hourly Cost**: AWS On-Demand pricing per instance type.
- **Waste Cost**:  
  - **Idle EC2** → `hourly_cost × 24` (for the daily reporting window).  
  - **Busy EC2** → `0`.  
  - **Unattached EBS** → full daily cost as waste.
- **CO₂ Emissions**: from AWS Sustainability + GHGP factors.  
  - Always tracked; only **idle/unattached** emissions are counted as **waste CO₂**.

> When hourly metrics are available, hours can be tallied precisely; with daily averages, the window is attributed as 24 busy or 24 idle.

---

## Pipeline
1. **Lambda** collects EC2/EBS inventory + CloudWatch metrics daily.  
2. Produces **cloud_cost_report.csv** → stored in **S3**.  
3. Streamlit dashboard loads the latest report (and optionally recent history) from S3 or local uploads.

---

## Assumptions & Limitations
- Costs use On-Demand pricing only (Spot/Savings plans not included).
- Using daily averages may hide short usage spikes. Hourly data improves accuracy.
- Waste thresholds (CPU 5%, Network 5 KB/s) are conservative defaults and can be adjusted.
""")
