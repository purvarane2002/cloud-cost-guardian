# report_writer.py
import csv, datetime

def write_cloud_cost_report(rows, filename="cloud_cost_report.csv"):
    """
    rows: list of dicts with keys:
      date, resource_type, resource_id, details, avg_cpu, avg_net_kbps,
      cost, co2, waste_cost, waste_co2
    """
    today = datetime.date.today().isoformat()
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Date","Resource Type","Resource ID","Details",
            "Avg CPU (24h)","Avg Network (KB/s)",
            "Est. Cost ($)","Est. CO2 (kg)",
            "Waste Cost ($)","Waste CO2 (kg)"
        ])
        if not rows:
            w.writerow([today,"None","None","No resources","N/A","N/A","N/A","N/A","N/A","N/A"])
            return

        for r in rows:
            w.writerow([
                r.get("date", today),
                r.get("resource_type","N/A"),
                r.get("resource_id","N/A"),
                r.get("details",""),
                f"{r['avg_cpu']:.2f}" if isinstance(r.get("avg_cpu"), (int,float)) else "N/A",
                f"{r['avg_net_kbps']:.2f}" if isinstance(r.get("avg_net_kbps"), (int,float)) else "N/A",
                f"{r['cost']:.4f}" if isinstance(r.get("cost"), (int,float)) else "N/A",
                f"{r['co2']:.4f}" if isinstance(r.get("co2"), (int,float)) else "N/A",
                f"{r['waste_cost']:.4f}" if isinstance(r.get("waste_cost"), (int,float)) else "N/A",
                f"{r['waste_co2']:.4f}" if isinstance(r.get("waste_co2"), (int,float)) else "N/A",
            ])

def write_analysis_summary(rows, filename="analysis_summary.csv"):
    """
    rows: list of dicts with keys:
      date, resource_type, resource_id, instance_type, utilization_pct, avg_net_kbps, hourly_cost, waste_cost, co2
    """
    today = datetime.date.today().isoformat()
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Date","Resource Type","Resource ID","Instance Type",
            "Utilization %","Avg Network (KB/s)","Hourly Cost ($)",
            "Estimated Cost Waste ($)","Estimated CO2 Emissions (kg)"
        ])

        if not rows:
            w.writerow([today,"None","None","None","N/A","N/A","N/A","N/A","N/A"])
            return

        for r in rows:
            w.writerow([
                r.get("date", today),
                r.get("resource_type","N/A"),
                r.get("resource_id","N/A"),
                r.get("instance_type","N/A"),
                f"{r['utilization_pct']:.2f}" if isinstance(r.get("utilization_pct"), (int,float)) else "N/A",
                f"{r['avg_net_kbps']:.2f}" if isinstance(r.get("avg_net_kbps"), (int,float)) else "N/A",
                f"{r['hourly_cost']:.4f}" if isinstance(r.get("hourly_cost"), (int,float)) else "N/A",
                f"{r['waste_cost']:.4f}" if isinstance(r.get("waste_cost"), (int,float)) else "N/A",
                f"{r['co2']:.4f}" if isinstance(r.get("co2"), (int,float)) else "N/A",
            ])
