# lambda_handler.py
import os
import boto3
import datetime

from run_report import build_reports  # returns file paths + row lists

s3 = boto3.client("s3")

def lambda_handler(event, context):
    """
    1) Generate both CSVs (saved to /tmp inside Lambda).
    2) Upload them to S3 using env vars:
       - CCG_BUCKET (your bucket name)
       - CCG_PREFIX (folder/prefix in the bucket)
    3) Return a small JSON summary.
    """

    # Build and write reports (run_report writes to /tmp now)
    cloud_path, analysis_path, ec2_rows, ebs_unattached_rows, ebs_attached_rows = build_reports()

    # ---- S3 destination (from Lambda environment variables) ----
    bucket = os.environ["CCG_BUCKET"]         # e.g. cloud-cost-guardian-reports
    prefix = os.environ.get("CCG_PREFIX", "") # e.g. reports
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    # Key names under the bucket/prefix
    cloud_key    = f"{prefix}cloud_cost_report.csv"
    analysis_key = f"{prefix}analysis_summary.csv"

    # ---- Upload the two files from /tmp to S3 ----
    s3.upload_file(cloud_path,    bucket, cloud_key)
    s3.upload_file(analysis_path, bucket, analysis_key)

    # ---- Return a short summary (handy in the Test tab) ----
    return {
        "status": "ok",
        "saved_to": {
            "cloud_cost_report":    f"s3://{bucket}/{cloud_key}",
            "analysis_summary_csv": f"s3://{bucket}/{analysis_key}",
        },
        "counts": {
            "ec2": len(ec2_rows),
            "ebs_unattached": len(ebs_unattached_rows),
            "ebs_attached": len(ebs_attached_rows),
        },
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }
