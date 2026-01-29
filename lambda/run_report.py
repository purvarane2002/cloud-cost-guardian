# run_report.py
import os
from datetime import date

from cloud_scan import get_ec2_instances
from ebs_scan import get_unattached_ebs_volumes, get_attached_ebs_volumes
# NOTE: keep this name if your function is called get_average_network_in_kbps in cloudwatch_metrics.py
from cloudwatch_metrics import get_average_cpu_usage, get_average_network_in_kbps
from estimators import (
    HOURS_PER_PERIOD,
    estimate_ec2_cost_and_emissions,
    estimate_ebs_cost_and_emissions,
    get_hourly_instance_price,
    is_instance_idle,
    ebs_waste_fraction,
)
from report_writer import write_cloud_cost_report, write_analysis_summary

TODAY = date.today().isoformat()

def _out(path: str) -> str:
    """
    Return a writable path. In AWS Lambda the code volume is read-only, so
    we must write to /tmp. Locally we keep the given filename.
    """
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return os.path.join("/tmp", path)
    return path

def _get_tag_bool(instance: dict, key: str) -> bool:
    """Read a boolean-ish tag (e.g., DoNotStop=True)."""
    for t in instance.get("Tags", []) or []:
        if t.get("Key") == key:
            return str(t.get("Value", "")).lower() in ("1", "true", "yes", "y")
    return False

def build_reports():
    """
    Builds both CSV reports and writes them to a writable location.
    Returns:
      (cloud_csv_path, analysis_csv_path, ec2_rows, ebs_unattached_rows, ebs_attached_rows)
    """
    cloud_rows = []
    analysis_rows = []

    # ---------- EC2 ----------
    ec2_data = get_ec2_instances()

    for inst in ec2_data:
        iid   = inst.get("InstanceId", "N/A")
        itype = inst.get("InstanceType", "N/A")
        state = inst.get("State", {}).get("Name", "N/A")
        excluded = _get_tag_bool(inst, "DoNotStop")

        avg_cpu = get_average_cpu_usage(iid, hours=int(HOURS_PER_PERIOD))
        avg_net = get_average_network_in_kbps(iid, hours=int(HOURS_PER_PERIOD))

        # Cost/CO2 (always)
        cost, co2 = estimate_ec2_cost_and_emissions(itype, hours=HOURS_PER_PERIOD)

        # Idle decision (two-signal) + tag exclusion
        idle = is_instance_idle(avg_cpu, avg_net)
        if excluded:
            idle = False  # force not idle if user says exclude

        waste_cost = cost if idle else 0.0
        waste_co2  = co2  if idle else 0.0

        # Cloud-cost report row (detailed)
        cloud_rows.append({
            "date": TODAY,
            "resource_type": "EC2",
            "resource_id": iid,
            "details": f"Type: {itype}, State: {state}" + (", Excluded: DoNotStop=True" if excluded else ""),
            "avg_cpu": avg_cpu,
            "avg_net_kbps": avg_net,
            "cost": cost,
            "co2":  co2,
            "waste_cost": waste_cost,
            "waste_co2":  waste_co2,
        })

        # Analysis summary row (compact)
        analysis_rows.append({
            "date": TODAY,
            "resource_type": "EC2",
            "resource_id": iid,
            "instance_type": itype,
            "utilization_pct": avg_cpu,
            "avg_net_kbps": avg_net,
            "hourly_cost": get_hourly_instance_price(itype),
            "waste_cost": waste_cost,
            "co2": co2,
        })

    # ---------- EBS ----------
    # Unattached => 100% waste for the period
    ebs_unattached = get_unattached_ebs_volumes() or []
    for v in ebs_unattached:
        vid  = v.get("VolumeId", "N/A")
        size = int(v.get("Size", 0))
        cost, co2 = estimate_ebs_cost_and_emissions(size, hours=HOURS_PER_PERIOD)
        frac = ebs_waste_fraction(attached=False)
        waste_cost, waste_co2 = cost * frac, co2 * frac

        cloud_rows.append({
            "date": TODAY,
            "resource_type": "EBS (unattached)",
            "resource_id": vid,
            "details": f"Size: {size} GB" if size else "Unattached EBS",
            "avg_cpu": None,
            "avg_net_kbps": None,
            "cost": cost,
            "co2": co2,
            "waste_cost": waste_cost,
            "waste_co2": waste_co2,
        })
        analysis_rows.append({
            "date": TODAY,
            "resource_type": "EBS (unattached)",
            "resource_id": vid,
            "instance_type": f"EBS {size}GB",
            "utilization_pct": None,
            "avg_net_kbps": None,
            "hourly_cost": None,
            "waste_cost": waste_cost,
            "co2": co2,
        })

    # Attached EBS => treat as 0% waste in Step 3
    ebs_attached = get_attached_ebs_volumes() or []
    for v in ebs_attached:
        vid  = v.get("VolumeId", "N/A")
        size = int(v.get("Size", 0))
        az   = v.get("AZ", "N/A")
        inst = v.get("AttachedTo", "N/A")
        cost, co2 = estimate_ebs_cost_and_emissions(size, hours=HOURS_PER_PERIOD)
        frac = ebs_waste_fraction(attached=True)
        waste_cost, waste_co2 = cost * frac, co2 * frac

        cloud_rows.append({
            "date": TODAY,
            "resource_type": "EBS (attached)",
            "resource_id": vid,
            "details": f"Size: {size} GB, AZ: {az}, AttachedTo: {inst}",
            "avg_cpu": None,
            "avg_net_kbps": None,
            "cost": cost,
            "co2":  co2,
            "waste_cost": waste_cost,
            "waste_co2":  waste_co2,
        })
        analysis_rows.append({
            "date": TODAY,
            "resource_type": "EBS (attached)",
            "resource_id": vid,
            "instance_type": f"EBS {size}GB",
            "utilization_pct": None,
            "avg_net_kbps": None,
            "hourly_cost": (cost / HOURS_PER_PERIOD) if HOURS_PER_PERIOD else None,
            "waste_cost": waste_cost,
            "co2": co2,
        })

    # ---------- Write both CSVs ----------
    cloud_csv_path    = _out("cloud_cost_report.csv")
    analysis_csv_path = _out("analysis_summary.csv")

    write_cloud_cost_report(cloud_rows,   filename=cloud_csv_path)
    write_analysis_summary(analysis_rows, filename=analysis_csv_path)

    # Return paths + row lists so the handler can upload and show counts
    return cloud_csv_path, analysis_csv_path, cloud_rows, ebs_unattached, ebs_attached


if __name__ == "__main__":
    cloud_p, analysis_p, *_ = build_reports()
    print(f"✅ Reports saved: {cloud_p}, {analysis_p}")
