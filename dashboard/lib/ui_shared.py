import streamlit as st
import pandas as pd

def render_filters(data: pd.DataFrame):
    st.sidebar.header("Filters")
    if "date" in data and data["date"].notna().any():
        dmin = pd.to_datetime(data["date"]).min().date()
        dmax = pd.to_datetime(data["date"]).max().date()
        date_range = st.sidebar.date_input("Date range", (dmin, dmax))
    else:
        date_range = None

    rtypes = sorted([x for x in data.get("resource_type", pd.Series(dtype=str)).dropna().unique()])
    itypes = sorted([x for x in data.get("instance_type", pd.Series(dtype=str)).dropna().unique()])

    rt_sel = st.sidebar.multiselect("Resource Type", rtypes, default=rtypes or None)
    it_sel = st.sidebar.multiselect("Instance Type", itypes)
    status = st.sidebar.selectbox("Status", ["All","Idle","Busy"], index=0)
    exclude_dns = st.sidebar.checkbox("Exclude DoNotStop=True", value=True)
    return dict(date_range=date_range, resource_types=rt_sel or None,
                instance_types=it_sel or None, status=status,
                exclude_do_not_stop=exclude_dns)

def kpi_row(m: dict):
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Rows", f"{m['rows']:,}")
    c2.metric("Total Cost (hr)", f"${m['hourly_cost_total']:.2f}")
    c3.metric("Waste Cost", f"${m['waste_cost_total']:.2f}")
    c4.metric("Total CO₂ (kg)", f"{m['co2_total']:.3f}")
    c5.metric("Waste CO₂ (kg)", f"{m['waste_co2_total']:.3f}")
