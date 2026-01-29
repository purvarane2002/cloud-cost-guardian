import streamlit as st
import pandas as pd
import plotly.express as px

from lib.s3_utils import list_csv_objects, read_csv
from lib.data_utils import (
    normalize, kpis,
    daily_waste_trend, waste_by_resource_type, share_by_status,
    load_reports_for_trend,   # use timestamped reports for trend
)

st.set_page_config(page_title="Cloud Cost Guardian", page_icon="🛡️", layout="wide")
st.title("🛡️ Cloud Cost Guardian — Overview")

# --- Sidebar: Data source ---
st.sidebar.header("Data source")
mode = st.sidebar.radio("Load from", ["S3 bucket", "Upload CSV"], index=0)

data = pd.DataFrame()
trend_data = pd.DataFrame()  # will become `data` or combined history

if mode == "S3 bucket":
    bucket = st.sidebar.text_input("S3 bucket", value="cloud-cost-guardian-reports")
    prefix = st.sidebar.text_input("Prefix", value="reports/")  # standard location
    region = st.sidebar.text_input("AWS Region", value="eu-west-2")

    if st.sidebar.button("Load latest"):
        # List newest-first and keep only cloud_cost_report*.csv
        items = list_csv_objects(bucket, prefix, region_name=region)
        keys = [k for (k, _, _) in items if "cloud_cost_report" in k.lower() and k.lower().endswith(".csv")]

        if not keys:
            st.warning("No cloud_cost_report CSVs found under this bucket/prefix.")
        else:
            key = keys[0]  # newest file
            data = normalize(read_csv(bucket, key, region_name=region))
            st.caption(f"Loaded latest: `{key}`")

            # --- History loader for trend (KPIs still use only 'data') ---
            include_history = st.sidebar.checkbox("Include history for trend", value=False)
            history_files = st.sidebar.number_input(
                "How many files (approx. days)?", min_value=2, max_value=90, value=30, step=1
            )

            trend_data = data  # default: only the latest
            if include_history:
                # Read merged timestamped reports and normalize once
                raw_hist, n_files = load_reports_for_trend(
                    bucket=bucket, prefix=prefix, max_files=int(history_files)
                )
                if not raw_hist.empty:
                    trend_data = normalize(raw_hist)
                    st.caption(f"Loaded {n_files} files for the trend.")
else:
    up = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if up:
        data = normalize(pd.read_csv(up))
        trend_data = data  # upload mode: trend == latest
        st.caption("Loaded uploaded file.")

# Nothing loaded?
if data.empty:
    st.info("Load a cloud_cost_report CSV (from S3 or upload) to continue.")
    st.stop()

# Ensure trend_data is usable even if history checkbox wasn’t shown yet
if trend_data.empty:
    trend_data = data.copy()

# --- Optional exclude toggle (apply to both latest + trend) ---
exclude_dns = st.sidebar.checkbox("Exclude DoNotStop=True", value=True)
if exclude_dns and "details" in data.columns:
    mask = ~data["details"].astype(str).str.contains("DoNotStop=True", case=False, na=False)
    data = data[mask]
    if "details" in trend_data.columns:
        mask_t = ~trend_data["details"].astype(str).str.contains("DoNotStop=True", case=False, na=False)
        trend_data = trend_data[mask_t]

# --- KPIs (from latest only) ---
m = kpis(data)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rows", f"{m['rows']:,}")
c2.metric("Total Cost (hr)", f"${m['hourly_cost_total']:.2f}")
c3.metric("Waste Cost", f"${m['waste_cost_total']:.2f}")
c4.metric("Total CO₂ (kg)", f"{m['co2_total']:.3f}")
c5.metric("Waste CO₂ (kg)", f"{m['waste_co2_total']:.3f}")

# ====================================================================
# Trend (last 30 calendar days)
# ====================================================================
st.subheader("Waste Trend (last 30 days)")
trend = daily_waste_trend(trend_data)  # latest OR combined history

with st.expander("Trend health (debug)", expanded=False):
    unique_days = int(trend["date"].dt.date.nunique()) if not trend.empty else 0
    st.write(f"Distinct days in trend data: **{unique_days}**")
    if unique_days >= 30:
        st.success("✅ 30-day trend is complete.")
    elif unique_days >= 7:
        st.warning("🟨 Partial trend (≥7 days). Keep collecting daily files to reach 30.")
    elif unique_days > 0:
        st.info("ℹ️ Fewer than 7 days so far. The line may look flat or sparse until more files accrue.")
    else:
        st.info("No trend data yet. Load historical files or wait for more daily runs.")

if not trend.empty and trend["date"].nunique() > 1:
    # Keep only the most recent 30 days for display
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=30)
    trend = trend[trend["date"] >= cutoff]
    fig = px.line(
        trend,
        x="date",
        y=["waste_cost", "waste_co2_kg"],
        labels={"value": "Amount", "variable": "Metric"},
    )
    fig.update_yaxes(title="Amount (hourly units)")
    fig.update_layout(xaxis_title="Date", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, key="trend_chart")
elif not trend.empty:
    st.info("Only one day of data detected. Load multiple daily reports to see a trend.")
else:
    st.info("No Date column found. Upload daily reports (e.g., 'cloud_cost_report.csv').")

# --- Pies (from latest only) ---
cA, cB = st.columns(2)
with cA:
    st.subheader("Waste by Resource Type")
    by_type = waste_by_resource_type(data)
    if not by_type.empty and by_type["waste_cost"].sum() > 0:
        fig2 = px.pie(by_type, values="waste_cost", names="resource_type", hole=0.35)
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig2, use_container_width=True, key="waste_type_chart")
    else:
        st.info("No waste recorded for this dataset.")

with cB:
    st.subheader("Idle vs Busy (waste share)")
    by_status = share_by_status(data)
    if not by_status.empty and by_status["waste_cost"].sum() > 0:
        fig3 = px.pie(by_status, values="waste_cost", names="status", hole=0.35)
        fig3.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig3, use_container_width=True, key="status_share_chart")
    else:
        st.info("No waste recorded for this dataset.")

# --- Download current dataset (latest only) ---
st.download_button(
    "Download latest dataset (CSV)",
    data=data.to_csv(index=False).encode("utf-8"),
    file_name="ccg_latest.csv",
    mime="text/csv",
)

st.caption(
    "Tip: KPIs & pies use the latest `cloud_cost_report*.csv`. "
    "Tick 'Include history for trend' to combine recent files for the line chart. "
    "The detailed table lives on the Analysis page."
)
