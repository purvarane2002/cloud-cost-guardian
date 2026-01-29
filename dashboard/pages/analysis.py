import streamlit as st
import pandas as pd
import plotly.express as px

from lib.s3_utils import list_csv_objects, read_csv
from lib.data_utils import (
    normalize,
    detailed_cloud_report_table,
)

st.title("📊 Analysis")

# ----------------------------
# Data source (S3 or local) — Prefer cloud_cost_report*, fallback to newest .csv
# ----------------------------
st.sidebar.header("Data source")
mode = st.sidebar.radio("Load from", ["S3 bucket", "Upload CSV"], index=0)

data = pd.DataFrame()
loaded_key = None

def _as_key(x):
    """Return the S3 key string from a string or (key, meta) tuple/list."""
    if isinstance(x, (tuple, list)) and x:
        return x[0]
    return x

def _try_list(bucket: str, pref: str):
    """Wrap list_csv_objects and ALWAYS return a list of key strings (newest first)."""
    try:
        items = list_csv_objects(bucket, pref or "")
        if not items:
            return []
        # Coerce to strings
        keys = [_as_key(i) for i in items if _as_key(i)]
        # De-dup just in case
        seen, out = set(), []
        for k in keys:
            if k not in seen:
                seen.add(k)
                out.append(k)
        return out
    except Exception as e:
        st.warning(f"Could not list objects under prefix '{pref}': {e}")
        return []

if mode == "S3 bucket":
    bucket = st.sidebar.text_input("S3 bucket", value="cloud-cost-guardian-reports")
    prefix = st.sidebar.text_input("Prefix (optional)", value="")
    show_debug = st.sidebar.checkbox("Show first 10 keys (debug)", value=False)

    if st.sidebar.button("Load latest"):
        # 1) Build search order: user prefix (if any) → 'reports/' → root
        search_order = [prefix] if prefix else []
        for p in ("reports/", ""):
            if p not in search_order:
                search_order.append(p)

        # 2) Try each prefix until we find any CSVs
        all_keys = []
        used_prefix = None
        for p in search_order:
            ks = _try_list(bucket, p)
            if ks:
                all_keys = ks
                used_prefix = p
                break

        if show_debug:
            st.info(
                "Debug listing:\n"
                f"- Tried prefixes (in order): {search_order}\n"
                f"- Using prefix: '{used_prefix if used_prefix is not None else '(none found)'}'\n"
                f"- First 10 keys: {all_keys[:10]}"
            )

        if not all_keys:
            st.warning("No CSV files found in the bucket. Check the bucket name, prefix, and IAM permissions.")
        else:
            # 3) Prefer keys containing 'cloud_cost_report' (any folder), else pick newest .csv
            preferred = [k for k in all_keys if "cloud_cost_report" in k]
            candidates = preferred if preferred else [k for k in all_keys if k.lower().endswith(".csv")]

            if not candidates:
                st.warning("No .csv files found. Upload a CSV or adjust the prefix.")
            else:
                key = candidates[0]  # newest by LastModified DESC per your util
                data = normalize(read_csv(bucket, key))
                loaded_key = key
                st.caption(f"Loaded latest: `{key}`")

else:
    up = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if up:
        data = normalize(pd.read_csv(up))
        loaded_key = "(uploaded file)"
        st.caption("Loaded uploaded file.")

if data.empty:
    st.info("Load a CSV (ideally a `cloud_cost_report.csv`) from S3 or upload to continue.")
    st.stop()

# ----------------------------
# Optional exclude toggle
# ----------------------------
exclude_dns = st.sidebar.checkbox("Exclude DoNotStop=True", value=True)
if exclude_dns and "details" in data.columns:
    data = data[~data["details"].astype(str).str.contains("DoNotStop=True", case=False, na=False)]
    
# ----------------------------
# Build the canonical detailed table (derives status; fills daily fields if missing)
# ----------------------------
base_table = detailed_cloud_report_table(data).copy()

# ----------------------------
# Filters
# ----------------------------
st.sidebar.subheader("Filters")
status_opts = sorted([x for x in base_table["status"].dropna().unique()]) if "status" in base_table else []
rtype_opts  = sorted([x for x in base_table["resource_type"].dropna().unique()]) if "resource_type" in base_table else []

status_sel = st.sidebar.multiselect("Status", status_opts)
rtype_sel  = st.sidebar.multiselect("Resource Type", rtype_opts)

filt = base_table.copy()
if status_sel:
    filt = filt[filt["status"].isin(status_sel)]
if rtype_sel:
    filt = filt[filt["resource_type"].isin(rtype_sel)]

if filt.empty:
    st.info("No rows after applying filters.")
    st.stop()

# ----------------------------
# Detailed table
# ----------------------------
st.subheader("Cloud Cost Report — Detailed Table")

fmt = filt.copy()
if "cpu" in fmt:             fmt["cpu"]            = fmt["cpu"].map(lambda x: f"{x:.2f}"   if pd.notna(x) else "")
if "network_kbps" in fmt:    fmt["network_kbps"]   = fmt["network_kbps"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "")
if "est_cost_day" in fmt:    fmt["est_cost_day"]   = fmt["est_cost_day"].map(lambda x: f"${x:.4f}" if pd.notna(x) else "")
if "est_co2_day" in fmt:     fmt["est_co2_day"]    = fmt["est_co2_day"].map(lambda x: f"{x:.4f}"   if pd.notna(x) else "")
if "waste_cost_day" in fmt:  fmt["waste_cost_day"] = fmt["waste_cost_day"].map(lambda x: f"${x:.4f}" if pd.notna(x) else "")
if "waste_co2_day" in fmt:   fmt["waste_co2_day"]  = fmt["waste_co2_day"].map(lambda x: f"{x:.4f}"   if pd.notna(x) else "")

cols = [
    "date","resource_type","resource_id","details",
    "cpu","network_kbps","est_cost_day","est_co2_day",
    "waste_cost_day","waste_co2_day","status",
]
cols = [c for c in cols if c in fmt.columns]
st.dataframe(fmt[cols], use_container_width=True)

st.download_button(
    "Download detailed table (CSV)",
    data=filt[cols].to_csv(index=False).encode("utf-8"),
    file_name="ccg_detailed_table.csv",
    mime="text/csv",
    key="dl_detailed_table",
)

# ----------------------------
# Bar chart — Top waste by resource
# ----------------------------
st.subheader("Top Waste by Resource")

top_n = st.slider("How many?", min_value=1, max_value=50, value=10, key="topn_bar")

agg = (
    filt.groupby(["resource_id"], dropna=False)
        .agg(
            waste_cost_day=("waste_cost_day", "sum"),
            resource_type=("resource_type", "first"),
        )
        .reset_index()
        .sort_values("waste_cost_day", ascending=False, na_position="last")
)

top_df = agg.head(top_n)

if top_df["waste_cost_day"].fillna(0).sum() <= 0:
    st.info("No non-zero waste to chart for the selected filters.")
else:
    fig = px.bar(
        top_df,
        x="resource_id",
        y="waste_cost_day",
        hover_data=["resource_type"],
    )
    fig.update_layout(
        yaxis_title="Waste Cost (daily $)",
        xaxis_title="Resource ID",
    )
    st.plotly_chart(fig, use_container_width=True, key="analysis_bar")

# Show which file was loaded
if loaded_key:
    st.caption(f"Source: {loaded_key}")
