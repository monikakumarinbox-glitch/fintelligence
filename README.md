# Fintelligence

AI workload optimization agent for financial services — monitors Gemini-powered 
workflows via Dynatrace and safely applies cost optimizations with compliance approval.

## Live Demo
https://fintelligence-775769240221.us-central1.run.app

## What it does
Fintelligence identifies waste in Gemini-powered financial services endpoints:
- Fraud detection using expensive Pro model for simple tasks
- Loan eligibility with cacheable repeated prompts  
- Wealth summaries with oversized token limits

## Tech Stack
- Google ADK — Agent orchestration
- Gemini via Vertex AI — Semantic request classification
- Dynatrace MCP — Runtime observability signals
- Python + Flask — Agent core and approval UI
- Google Cloud Run — Hosting

## Setup

### Prerequisites
- Python 3.11+
- Google Cloud account
- Dynatrace account

### Run locally
```bash
git clone https://github.com/monikakumarinbox-glitch/fintelligence.git
cd fintelligence

pip install flask google-cloud-aiplatform google-adk google-genai \
    requests tenacity python-dotenv opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-http mcp

export DEMO_MODE=true
export DT_ENDPOINT=https://YOUR_ENV.live.dynatrace.com
export DT_API_TOKEN=your_token
export GCP_PROJECT_ID=your_project_id

cd ui
python app.py
```

Open http://localhost:5000

### Deploy to Cloud Run
```bash
gcloud run deploy fintelligence \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DEMO_MODE=true,DT_ENDPOINT=your_dt_url,DT_API_TOKEN=your_token
```

## License
MIT
