# dashboard/lib/s3_utils.py
import io
import boto3
import pandas as pd

def _client(region_name=None, endpoint_url=None):
    # Let AWS creds/region come from env/instance role; override if passed
    return boto3.client("s3", region_name=region_name, endpoint_url=endpoint_url)

def list_csv_objects(bucket: str, prefix: str = "", max_keys: int = 1000, region_name=None, endpoint_url=None):
    """
    Returns a list of (key, size, last_modified) for .csv objects under prefix.
    Sorted by last_modified DESC.
    """
    s3 = _client(region_name, endpoint_url)
    keys = []
    cont = None
    while True:
        kwargs = dict(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
        if cont:
            kwargs["ContinuationToken"] = cont
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            if obj["Key"].lower().endswith(".csv"):
                keys.append((obj["Key"], obj["Size"], obj["LastModified"]))
        if resp.get("IsTruncated"):
            cont = resp.get("NextContinuationToken")
        else:
            break
    keys.sort(key=lambda x: x[2], reverse=True)
    return keys

def read_csv(bucket: str, key: str, region_name=None, endpoint_url=None) -> pd.DataFrame:
    s3 = _client(region_name, endpoint_url)
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    # pandas will auto-detect utf-8/latin-1 in most cases; tweak if needed
    return pd.read_csv(io.BytesIO(body))

def read_all_csvs(bucket: str, prefix: str = "", limit: int | None = None, region_name=None, endpoint_url=None) -> list[pd.DataFrame]:
    """
    Reads all (or first N) CSVs under prefix, newest first.
    Returns a list of DataFrames (one per file).
    """
    items = list_csv_objects(bucket, prefix, region_name=region_name, endpoint_url=endpoint_url)
    if limit is not None:
        items = items[:limit]
    out = []
    for key, *_ in items:
        try:
            df = read_csv(bucket, key, region_name=region_name, endpoint_url=endpoint_url)
            df["source_key"] = key  # optional: track file of origin
            out.append(df)
        except Exception as e:
            # don't break on one bad file
            print(f"[WARN] Failed to read {key}: {e}")
    return out
