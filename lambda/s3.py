# s3.py – upload/list/download reports in S3
import os
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

BUCKET = "cloud-cost-guardian-reports"
PREFIX = "reports/"                     # keep trailing slash
REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-2")

s3 = boto3.client("s3", region_name=REGION)

def _ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")

def _upload_one(local_path: str, base_name: str, timestamped: bool = True):
    if not os.path.exists(local_path):
        print(f"⚠️  Skipping: {local_path} not found.")
        return

    if timestamped:
        ts_key = f"{PREFIX}{base_name.replace('.csv','')}-{_ts()}.csv"
        print(f"Uploading {local_path}  →  s3://{BUCKET}/{ts_key}")
        s3.upload_file(local_path, BUCKET, ts_key)

        latest_key = f"{PREFIX}{base_name}"
        print(f"Copying to latest       →  s3://{BUCKET}/{latest_key}")
        s3.copy_object(Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": ts_key}, Key=latest_key)
    else:
        key = f"{PREFIX}{base_name}"
        print(f"Uploading {local_path}  →  s3://{BUCKET}/{key}")
        s3.upload_file(local_path, BUCKET, key)

def upload_reports(timestamped: bool = True):
    """Upload both CSVs: cloud_cost_report.csv and analysis_summary.csv."""
    _upload_one("cloud_cost_report.csv", "cloud_cost_report.csv", timestamped=timestamped)
    _upload_one("analysis_summary.csv", "analysis_summary.csv", timestamped=timestamped)
    print("✅ Upload complete.")

def list_reports(max_keys: int = 50):
    print(f"Listing s3://{BUCKET}/{PREFIX}")
    try:
        resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX, MaxKeys=max_keys)
        for obj in sorted(resp.get("Contents", []), key=lambda x: x["LastModified"], reverse=True):
            when = obj["LastModified"].strftime("%Y-%m-%d %H:%M:%S %Z")
            size = obj["Size"]
            print(f"{when:20}  {size:8}  s3://{BUCKET}/{obj['Key']}")
    except ClientError as e:
        print("S3 error:", e)

def download_latest(which: str = "analysis_summary"):
    """
    Download the latest version of a report.
    which: 'analysis_summary' or 'cloud_cost_report'
    Saves to ./latest_<which>.csv
    """
    latest_key = f"{PREFIX}{which}.csv"
    local = f"latest_{which}.csv"
    try:
        s3.head_object(Bucket=BUCKET, Key=latest_key)
        print(f"Downloading s3://{BUCKET}/{latest_key} → {local}")
        s3.download_file(BUCKET, latest_key, local)
        print("✅ Download complete.")
        return local
    except ClientError:
        print(f"⚠️  Latest key not found: s3://{BUCKET}/{latest_key}")
        return None

if __name__ == "__main__":
    upload_reports(timestamped=True)
    list_reports()
