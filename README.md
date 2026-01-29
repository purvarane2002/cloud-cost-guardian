# ☁️ Cloud Cost Guardian

Cloud Cost Guardian is an automated cloud analytics system that monitors AWS infrastructure usage, identifies underutilised resources, and links them to financial cost and CO₂ impact.

It helps engineers and organisations make data-driven decisions to reduce cloud waste and improve sustainability.

---

## 🚀 Features

- ✅ Collects EC2 & EBS usage via AWS CloudWatch  
- ✅ Runs on a scheduled basis using AWS Lambda & EventBridge  
- ✅ Detects idle and underutilised resources  
- ✅ Estimates avoidable cloud spend  
- ✅ Calculates associated carbon emissions  
- ✅ Presents insights in an interactive Streamlit dashboard  

---

## 🏗️ System Architecture

1. AWS Lambda functions scan EC2/EBS and CloudWatch metrics  
2. Usage data is processed using Python (Boto3)  
3. Cost and carbon estimates are calculated  
4. Results are stored and made available to the dashboard  
5. Streamlit dashboard visualises insights  

---

## 📁 Repository Structure

cloud-cost-guardian/
│
├── dashboard/ # Streamlit analytics dashboard
├── lambda/ # AWS Lambda scanning & reporting scripts
├── scripts/ # Local helper scripts (optional)
├── docs/ # Documentation assets
├── Dockerfile # Container configuration
└── manifest.json # Deployment metadata


---

## ▶️ Run Locally (Dashboard)

### Prerequisites
- Python 3.8+
- AWS credentials configured
- Streamlit installed

### Steps

```bash
cd dashboard
python -m pip install -r requirements.txt
streamlit run app.py
Then open: http://localhost:8501

⚙️ Tech Stack
Python

AWS (EC2, Lambda, S3, CloudWatch, EventBridge)

Streamlit

Boto3

Docker

📊 Example Use Cases
Identify unused EC2 instances

Detect oversized volumes

Track cloud waste trends

Support sustainability reporting

Reduce monthly AWS bills

🎯 Why This Project
During my MSc, I observed that cloud cost optimisation and sustainability are often treated as separate problems.

This project connects infrastructure usage, financial waste, and environmental impact into a single analytics system, enabling practical, measurable optimisation.

📌 Future Improvements
Add multi-account support

Integrate AWS Cost Explorer

Add alerting system

Improve carbon estimation models

Deploy fully serverless dashboard

👤 Author
Purva Rane
MSc Software Engineering (Cloud Computing)
GitHub: https://github.com/purvarane2002
