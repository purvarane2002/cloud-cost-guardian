# dashboard/lib/data_utils.py
import io
import re
from datetime import datetime, timezone

import boto3  # for S3 loading
import pandas as pd
from dateutil import parser


def _s(val) -> str:
    """Safe string: handle pandas.NA/NaN/None"""
    try:
        if val is pd.NA or pd.isna(val):
            return ""
    except Exception:
        pass
    return "" if val is None else str(val)


# Thresholds to compute Idle/Busy when status is missing
CPU_IDLE = 5.0       # %
NET_IDLE = 5.0       # KB/s


# Accept both your legacy headers and the new ones
MAP = {
    "date": ["Date", "date", "timestamp", "run_date"],

    "resource_id": ["Resource ID", "resource_id", "InstanceId", "VolumeId"],
    "resource_type": ["Resource Type", "resource_type", "Type"],
    "details": ["Details", "details"],
    "status": ["Status", "status"],

    # Instance type sometimes only appears inside Details
    "instance_type": ["Instance Type", "instance_type"],

    # Metrics
    # ✅ Added "Utilization %" so analysis_summary.csv feeds the CPU/Utilization logic
    "cpu": ["CPU %", "Avg CPU (24h)", "CPU", "cpu", "cpu_percent", "Utilization %"],
    "network_kbps": [
        "Network (KB/s)",
        "Avg Network (24h) (KB/s)",
        "Avg Network (KB/s)",
        "Avg Network",
        "Network",
        "Net KB/s",
        "network_kbps",
    ],

    # Hourly cost
    # ✅ Added "Hourly Cost ($)" to catch that header variant
    "hourly_cost": ["Hourly Cost", "Hourly Cost ($)", "hourly_cost", "Cost (Hourly)", "Cost/hour", "Cost hr"],

    # Hourly CO2
    "co2_hour": [
        "CO2 (kg)", "CO₂ (kg)", "co2_kg",
        "Estimated CO2 Emissions (kg)", "Estimated CO₂ Emissions (kg)"
    ],

    # Hourly waste (analysis summary)
    "waste_cost_hour": ["Waste Cost", "waste_cost", "Waste Cost (Hourly)", "waste_cost_hour"],
    "waste_co2_hour": ["Waste CO2 (kg)", "Waste CO₂ (kg)", "waste_co2_kg", "waste_co2_hour"],

    # Daily (cloud_cost_report)
    "est_cost_day": ["Est. Cost ($)", "Estimated Daily Cost", "daily_cost"],
    "est_co2_day": ["Est. CO2 (kg)", "co2_day"],
    # ✅ Added "Estimated Cost Waste ($)" so daily waste from analysis_summary.csv is recognized
    "waste_cost_day": ["Waste Cost ($)", "Estimated Cost Waste ($)", "waste_cost_day"],
    "waste_co2_day": ["Waste CO2 (kg)", "waste_co2_day"],
}


def _pick(df, names):
    for n in names:
        if n in df.columns:
            return n


def _coalesce_duplicate_columns(df: pd.DataFrame, colname: str) -> pd.DataFrame:
    """
    If multiple columns share the same name (e.g., after renaming),
    merge them left→right using combine_first and keep a single column.

    IMPORTANT: select by **positional index** so we get Series objects even when
    duplicate names exist (df['name'] would return a DataFrame).
    """
    idxs = [i for i, c in enumerate(df.columns) if c == colname]
    if len(idxs) <= 1:
        return df

    base = df.iloc[:, idxs[0]].copy()
    for i in idxs[1:]:
        base = base.combine_first(df.iloc[:, i])

    # Drop all duplicates by position, then insert the merged column once
    df = df.drop(columns=[df.columns[i] for i in idxs])
    df[colname] = base
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Map whatever headers your CSV has to a consistent internal set."""
    src = df.copy()
    ren = {}
    for canon, cands in MAP.items():
        c = _pick(src, cands)
        if c:
            ren[c] = canon
    df = src.rename(columns=ren)

    # 🔧 Collapse duplicates created by renaming (especially 'date')
    for key in ["date", "resource_id", "resource_type", "details", "status", "instance_type"]:
        df = _coalesce_duplicate_columns(df, key)

    # Ensure expected keys exist
    for k in MAP.keys():
        if k not in df.columns:
            df[k] = pd.NA

    # Parse date (single column after coalescing)
    if df["date"].notna().any():
        df["date"] = pd.to_datetime(
            df["date"].apply(lambda x: parser.parse(str(x)) if pd.notna(x) else pd.NaT),
            errors="coerce"
        )

    # Numeric coercion
    for col in [
        "cpu", "network_kbps", "hourly_cost", "co2_hour",
        "waste_cost_hour", "waste_co2_hour",
        "est_cost_day", "est_co2_day", "waste_cost_day", "waste_co2_day"
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ---------- Derivation helpers (to make dashboards robust) ----------

def _derive_status(row: pd.Series) -> str:
    """If status missing, compute Idle/Busy from metrics/resource type + details hints."""
    s = _s(row.get("status")).strip()
    if s:
        return s

    rtype = _s(row.get("resource_type"))
    cpu = row.get("cpu")
    net = row.get("network_kbps")
    details = _s(row.get("details")).lower()

    # EBS
    if "ebs" in rtype.upper():
        return "Idle" if "unattached" in details or "unattached" in rtype.lower() else "Busy"

    # Strong textual hints from details (covers EC2 stopped, unused, etc.)
    detail_idle_hints = ("stopped", "stop ", "unused", "idle", "powered off", "power off",
                         "not running", "shut down", "shutdown", "terminated")
    if any(h in details for h in detail_idle_hints):
        return "Idle"

    # Metrics-based rule for EC2/other
    cpu_ok = pd.notna(cpu) and cpu < CPU_IDLE
    net_ok = pd.notna(net) and net < NET_IDLE
    if cpu_ok and net_ok:
        return "Idle"

    # If BOTH metrics are missing, treat as Idle (no telemetry -> assume waste unless proven busy)
    if pd.isna(cpu) and pd.isna(net):
        return "Idle"

    return "Busy"



def _derive_instance_type(row: pd.Series) -> str:
    """If instance_type missing, try to parse from Details."""
    it = _s(row.get("instance_type")).strip()
    if it:
        return it

    details = _s(row.get("details"))
    # Example: "Type: t3.micro, State: running"
    m = re.search(r"Type:\s*([^,]+)", details, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Example: "Size: 8 GB, State: in-use, AZ: ..."
    m = re.search(r"Size:\s*(\d+)\s*GB", details, flags=re.IGNORECASE)
    if m:
        return f"EBS {m.group(1)}GB"
    return ""


def _effective_hourly_cost(row: pd.Series) -> float:
    """Pick hourly cost if present; else derive from daily/24; else 0."""
    if pd.notna(row.get("hourly_cost")):
        return float(row["hourly_cost"])
    if pd.notna(row.get("est_cost_day")):
        return float(row["est_cost_day"]) / 24.0
    return 0.0


def _effective_hourly_co2(row: pd.Series) -> float:
    """Pick hourly CO2 if present; else daily/24; else 0."""
    if pd.notna(row.get("co2_hour")):
        return float(row["co2_hour"])
    if pd.notna(row.get("est_co2_day")):
        return float(row["est_co2_day"]) / 24.0
    return 0.0

def _effective_waste_hourly(row: pd.Series) -> float:
    """Unified hourly waste: prefer explicit hourly; else daily/24; else compute from status."""
    if pd.notna(row.get("waste_cost_hour")):
        return float(row["waste_cost_hour"])
    if pd.notna(row.get("waste_cost_day")):
        return float(row["waste_cost_day"]) / 24.0
    # Compute from status
    status = _derive_status(row)
    if status == "Idle":
        return _effective_hourly_cost(row)
    return 0.0


def _effective_waste_co2_hourly(row: pd.Series) -> float:
    if pd.notna(row.get("waste_co2_hour")):
        return float(row["waste_co2_hour"])
    if pd.notna(row.get("waste_co2_day")):
        return float(row["waste_co2_day"]) / 24.0
    status = _derive_status(row)
    if status == "Idle":
        return _effective_hourly_co2(row)
    return 0.0

def _exclusion_note(s: pd.Series) -> pd.Series:
    # Return "(Excluded: DoNotStop=True)" if present in Details; else ""
    contains = s.fillna("").astype(str).str.contains("Excluded: DoNotStop=True", case=False)
    return contains.map(lambda x: "(Excluded: DoNotStop=True)" if x else "")


# ---------- Detection & table builders ----------

def is_cloud_cost_report(df: pd.DataFrame) -> bool:
    """
    Heuristic: treat as cloud_cost_report if it contains daily fields
    (est_cost_day / waste_cost_day) with any non-null values.
    """
    if "est_cost_day" in df.columns and df["est_cost_day"].notna().any():
        return True
    if "waste_cost_day" in df.columns and df["waste_cost_day"].notna().any():
        return True
    # Fallback: if there is a parsed date for many rows, assume daily report
    if "date" in df.columns and df["date"].notna().sum() >= max(1, int(len(df) * 0.5)):
        return True
    return False


def detailed_cloud_report_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Canonical daily table for cloud_cost_report.csv.
    - Preserve 'details' from the source (if present).
    - Recompute status from metrics/rules (ignore incoming Status).
    - Fill daily estimates if missing by deriving from unified hourly logic.
    """
    tmp = normalize(df).copy()

    # Ensure 'details' exists so the table always shows the context column
    if "details" not in tmp.columns:
        tmp["details"] = pd.NA

    # Always recompute status from metrics/simple rules
    tmp["status"] = tmp.apply(_derive_status, axis=1)

    # ---- Fill DAILY estimates when missing (derive from hourly × 24)
    # cost/day
    tmp["est_cost_day"] = tmp.apply(
        lambda r: r["est_cost_day"]
        if pd.notna(r.get("est_cost_day"))
        else _effective_hourly_cost(r) * 24.0,
        axis=1,
    )

    # CO2/day
    tmp["est_co2_day"] = tmp.apply(
        lambda r: r["est_co2_day"]
        if pd.notna(r.get("est_co2_day"))
        else _effective_hourly_co2(r) * 24.0,
        axis=1,
    )

    # waste cost/day
    tmp["waste_cost_day"] = tmp.apply(
        lambda r: r["waste_cost_day"]
        if pd.notna(r.get("waste_cost_day"))
        else _effective_waste_hourly(r) * 24.0,
        axis=1,
    )

    # waste CO2/day
    tmp["waste_co2_day"] = tmp.apply(
        lambda r: r["waste_co2_day"]
        if pd.notna(r.get("waste_co2_day"))
        else _effective_waste_co2_hourly(r) * 24.0,
        axis=1,
    )

    # Keep only rows with an id and the expected column order
    cols = [
        "date", "resource_type", "resource_id", "details",
        "cpu", "network_kbps", "est_cost_day", "est_co2_day",
        "waste_cost_day", "waste_co2_day", "status",
    ]
    cols = [c for c in cols if c in tmp.columns]
    tmp = tmp[tmp["resource_id"].notna()]

    return tmp[cols]


# ---------- S3 loaders (merge timestamped reports for trend) ----------

def load_all_reports(bucket, prefix="reports/"):
    """
    Simple loader: concatenates ALL timestamped cloud_cost_report_*.csv via s3fs URL.
    Requires s3fs installed if used.
    """
    s3 = boto3.client("s3")
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    dfs = []
    for obj in response.get("Contents", []):
        key = obj["Key"]
        if key.endswith(".csv") and "cloud_cost_report_" in key:  # only timestamped reports
            # This path uses s3fs; keep for backwards compatibility
            tmp = pd.read_csv(f"s3://{bucket}/{key}")
            dfs.append(tmp)

    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()


# --- TREND LOADER: read N newest timestamped reports and inject 'date' ---

_FILENAME_DATE_RE = re.compile(r"cloud_cost_report_(\d{4}-\d{2}-\d{2})\.csv$", re.IGNORECASE)

def _s3_list_all(bucket: str, prefix: str):
    s3 = boto3.client("s3")
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for o in resp.get("Contents", []):
            yield o
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")


def _read_csv_s3(bucket: str, key: str) -> pd.DataFrame:
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(io.BytesIO(obj["Body"].read()))


def load_reports_for_trend(bucket: str, prefix: str = "reports/", max_files: int = 30) -> tuple[pd.DataFrame, int]:
    """
    Merge newest `max_files` timestamped cloud_cost_report_*.csv into one DF.
    Ensures a non-null 'date' column per file (from filename or LastModified).
    Returns (df, files_read).
    """
    # collect candidates
    cands = []
    for o in _s3_list_all(bucket, prefix):
        k = o["Key"]
        if k.endswith(".csv") and "cloud_cost_report_" in k:
            cands.append((k, o.get("LastModified")))

    if not cands:
        return pd.DataFrame(), 0

    # newest first
    cands.sort(key=lambda x: x[1] or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
    keys = [k for k, _ in cands[:max_files]]

    dfs = []
    for key in keys:
        df = _read_csv_s3(bucket, key)

        # inject/repair date
        needs_date = ("date" not in df.columns) or df["date"].isna().all()
        m = _FILENAME_DATE_RE.search(key.split("/")[-1])
        if m:
            run_date = pd.to_datetime(m.group(1))
        else:
            lm = next((lm for k2, lm in cands if k2 == key), None)
            # LastModified is timezone-aware; convert to naive date
            run_date = (pd.to_datetime(lm).tz_convert(None).normalize() if lm is not None else pd.NaT)
        if needs_date:
            df["date"] = run_date

        dfs.append(df)

    return (pd.concat(dfs, ignore_index=True), len(keys))


# ---------- Public functions used by pages ----------

def minimal_analysis_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Exactly the columns you want for Analysis (short view):
    resource_id, status, instance_type, resource_type, hourly_cost, waste_cost, waste_co2_kg, details(note)
    """
    tmp = df.copy()

    # Fill derived fields row-wise
    status = tmp.apply(_derive_status, axis=1)
    inst = tmp.apply(_derive_instance_type, axis=1)
    hourly = tmp.apply(_effective_hourly_cost, axis=1)
    waste = tmp.apply(_effective_waste_hourly, axis=1)
    waste_co2 = tmp.apply(_effective_waste_co2_hourly, axis=1)
    note = _exclusion_note(tmp.get("details", pd.Series([""] * len(tmp))))

    out = pd.DataFrame({
        "resource_id":   tmp["resource_id"],
        "status":        status,
        "instance_type": inst,
        "resource_type": tmp["resource_type"],
        "hourly_cost":   hourly,
        "waste_cost":    waste,
        "waste_co2_kg":  waste_co2,
        "details":       note,
    })
    return out.sort_values("waste_cost", ascending=False, na_position="last").reset_index(drop=True)


def top_table_for_home(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """
    Home table (Top N): same field logic as minimal table, grouped by resource.
    """
    tmp = minimal_analysis_table(df)  # reuses all derivations
    g = tmp.groupby("resource_id", dropna=False).agg({
        "status": "first",
        "instance_type": "first",
        "resource_type": "first",
        "hourly_cost": "mean",
        "waste_cost": "sum",
        "waste_co2_kg": "sum",
    }).reset_index()
    return g.sort_values("waste_cost", ascending=False, na_position="last").head(n)


def kpis(df: pd.DataFrame) -> dict:
    """
    KPIs shown on Home: all in HOURLY units to be consistent across files.
    """
    tmp = df.copy()

    hourly = tmp.apply(_effective_hourly_cost, axis=1)
    waste = tmp.apply(_effective_waste_hourly, axis=1)
    co2 = tmp.apply(_effective_hourly_co2, axis=1)
    waste_co2 = tmp.apply(_effective_waste_co2_hourly, axis=1)

    return {
        "rows": int(len(tmp)),
        "hourly_cost_total": float(hourly.sum(skipna=True)),
        "waste_cost_total": float(waste.sum(skipna=True)),
        "co2_total": float(co2.sum(skipna=True)),
        "waste_co2_total": float(waste_co2.sum(skipna=True)),
    }


# ---------- Chart helpers (use unified hourly derivations) ----------

def daily_waste_trend(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns daily sums of waste_cost and waste_co2_kg (hourly units aggregated by day).
    If no date column, returns empty df.
    """
    if "date" not in df.columns or df["date"].isna().all():
        return pd.DataFrame(columns=["date", "waste_cost", "waste_co2_kg"])

    tmp = df.copy()
    tmp["_waste"] = tmp.apply(_effective_waste_hourly, axis=1)
    tmp["_waste_co2"] = tmp.apply(_effective_waste_co2_hourly, axis=1)

    g = tmp.groupby(pd.Grouper(key="date", freq="D")).agg(
        waste_cost=("_waste", "sum"),
        waste_co2_kg=("_waste_co2", "sum"),
    ).reset_index()

    return g.sort_values("date")


def waste_by_resource_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns total hourly waste cost grouped by resource_type (EC2 / EBS ...).
    """
    tmp = df.copy()
    tmp["_waste"] = tmp.apply(_effective_waste_hourly, axis=1)
    g = tmp.groupby("resource_type", dropna=False)["_waste"].sum().reset_index()
    g = g.rename(columns={"_waste": "waste_cost"}).sort_values("waste_cost", ascending=False)
    return g


def share_by_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns total hourly waste cost grouped by derived status (Idle/Busy).
    """
    tmp = df.copy()
    tmp["_status"] = tmp.apply(_derive_status, axis=1)
    tmp["_waste"] = tmp.apply(_effective_waste_hourly, axis=1)
    g = tmp.groupby("_status")["_waste"].sum().reset_index()
    g = g.rename(columns={"_status": "status", "_waste": "waste_cost"})
    return g


def top_waste_bar(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """
    Returns top N resources by hourly waste cost for a bar chart.
    """
    tmp = df.copy()
    tmp["_waste"] = tmp.apply(_effective_waste_hourly, axis=1)
    g = tmp.groupby("resource_id", dropna=False).agg(
        waste_cost=("_waste", "sum"),
        instance_type=("instance_type", "first"),
        resource_type=("resource_type", "first"),
    ).reset_index().sort_values("waste_cost", ascending=False).head(n)
    return g
