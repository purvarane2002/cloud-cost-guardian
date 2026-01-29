# cloudwatch_metrics.py
import boto3
from datetime import datetime, timedelta, timezone

# One shared client (uses your default CLI creds/region)
_session = boto3.Session()
_cw = _session.client("cloudwatch")

def _avg_from_datapoints(dps, key="Average"):
    if not dps:
        return None
    return sum(dp.get(key, 0.0) for dp in dps) / len(dps)

def get_average_cpu_usage(instance_id: str, hours: int = 24):
    """
    Average CPUUtilization (%) over the last <hours>.
    Returns float (0–100) or None if no data.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    resp = _cw.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start,
        EndTime=end,
        Period=3600,           # 1h buckets
        Statistics=["Average"]
    )
    return _avg_from_datapoints(resp.get("Datapoints", []), "Average")

def get_average_network_in_kbps(instance_id: str, hours: int = 24):
    """
    Average NetworkIn (KB/s) over the last <hours>.
    CloudWatch 'Average' for NetworkIn is bytes/second over the period.
    We convert to KB/s (bytes / 1024).
    Returns float or None if no data.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    resp = _cw.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="NetworkIn",
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start,
        EndTime=end,
        Period=3600,           # 1h buckets
        Statistics=["Average"] # bytes/second
    )
    avg_bps = _avg_from_datapoints(resp.get("Datapoints", []), "Average")
    if avg_bps is None:
        return None
    return float(avg_bps) / 1024.0  # KB/s
