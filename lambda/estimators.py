# estimators.py
import os
from typing import Tuple, Optional

# === Config (easy to cite in your dissertation) ===
HOURS_PER_PERIOD = float(os.getenv("CCG_HOURS_PER_PERIOD", "24"))  # analysis window (hours)

# Underutilization thresholds
UNDERUTIL_CPU_THRESHOLD = float(os.getenv("CCG_UNDERUTIL_CPU_THRESHOLD", "0.20"))  # 20% CPU
LOW_NETWORK_KBPS_THRESHOLD = float(os.getenv("CCG_LOW_NETWORK_KBPS_THRESHOLD", "1.0"))  # ~1 KB/s

# --- EC2 on-demand $/hour (illustrative; adjust per region if desired) ---
INSTANCE_PRICES = {
    "t2.micro": 0.0116,
    "t3.micro": 0.0104,
}

# --- EBS gp3 ballpark storage price ---
EBS_GB_MONTH = 0.10
HOURS_PER_MONTH = 730.0
EBS_GB_HOUR = EBS_GB_MONTH / HOURS_PER_MONTH  # ~ $0.000137 per GB-hour

# --- CO2 factors (illustrative — justify in methodology) ---
INSTANCE_CO2_KG_PER_HOUR = 0.0004     # tiny instance footprint per hour
EBS_CO2_KG_PER_GB_HOUR  = 0.00001     # per GB-hour

# ===================== Pricing helpers =====================

def get_hourly_instance_price(instance_type: str) -> float:
    """Return $/hour for an EC2 type (simple lookup)."""
    return float(INSTANCE_PRICES.get(instance_type, 0.0))

def estimate_ec2_cost_and_emissions(instance_type: str, hours: Optional[float] = None) -> Tuple[float, float]:
    """
    Total cost & total CO2 (not 'waste') over 'hours' for an EC2 instance.
    """
    hrs = HOURS_PER_PERIOD if hours is None else float(hours)
    cost = get_hourly_instance_price(instance_type) * hrs
    co2  = INSTANCE_CO2_KG_PER_HOUR * hrs
    return cost, co2

def estimate_ebs_cost_and_emissions(size_gb: int, hours: Optional[float] = None) -> Tuple[float, float]:
    """
    Total cost & total CO2 (not 'waste') over 'hours' for an EBS volume.
    """
    hrs = HOURS_PER_PERIOD if hours is None else float(hours)
    cost = EBS_GB_HOUR * float(size_gb) * hrs
    co2  = EBS_CO2_KG_PER_GB_HOUR * float(size_gb) * hrs
    return cost, co2

# ===================== Idle / waste decision =====================

def is_instance_idle(avg_cpu_pct: Optional[float], avg_net_kbps: Optional[float]) -> bool:
    """
    Two-signal idle decision:
      - CPU below threshold  (e.g., < 20%)
      - Network below threshold (e.g., < 1 KB/s)
    Missing data => treat as not idle (be conservative).
    """
    if avg_cpu_pct is None or avg_net_kbps is None:
        return False
    return (avg_cpu_pct < (UNDERUTIL_CPU_THRESHOLD * 100.0)) and (avg_net_kbps < LOW_NETWORK_KBPS_THRESHOLD)

def ebs_waste_fraction(attached: bool) -> float:
    """
    100% waste if unattached, 0% if attached (Step-3 simplification).
    """
    return 0.0 if attached else 1.0
