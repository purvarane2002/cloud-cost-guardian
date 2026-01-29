import streamlit as st
st.title("⚙️ System (Pipeline & Security)")

st.markdown("""
### Data pipeline
1. Every day, an AWS Lambda function collects usage data for EC2 and EBS from CloudWatch.
2. It applies the waste detection rules (idle vs busy EC2, attached vs unattached EBS) and calculates cost and CO₂.
3. The results are stored in S3 as a CSV file (cloud_cost_report.csv).

### Schedule
- AWS EventBridge triggers the Lambda automatically once per day, so the process runs without manual work.

### Dashboard
- The Streamlit dashboard loads reports directly from S3 or local CSV files.
- All filters, KPIs, and charts are calculated inside the dashboard in real time.
            

### Security
- Access to the S3 reports bucket is restricted with a read-only IAM policy.
- No passwords or keys are hard-coded; in production the system uses secure instance roles.
- The dashboard is containerised with Docker and deployed on AWS App Runner, which provides HTTPS by default.

### Deployment (summary)
- The dashboard is packaged into a Docker image.
- The image is pushed to Amazon ECR (Elastic Container Registry).
- AWS App Runner then runs the container as a web service (port 8501), using the instance role for secure access.).
""")
