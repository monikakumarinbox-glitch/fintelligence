# Fintelligence

AI workload optimization agent for financial services — monitors Gemini-powered 
workflows via Dynatrace MCP and safely applies cost optimizations with compliance approval.

## Live Demo
🚀 **https://fintelligence-775769240221.us-central1.run.app**

> Note: First load may take 10-15 seconds as the service wakes up from idle.

## Live Stack (all called at runtime)
| Component | Technology | Status |
|---|---|---|
| Observability | Dynatrace MCP (18 tools, real-time) | ✅ Live |
| AI Classification | Gemini 2.5 Flash via Vertex AI | ✅ Live |
| Orchestration | Google Cloud ADK | ✅ Live |
| Hosting | Google Cloud Run | ✅ Live |

Verify at: https://fintelligence-775769240221.us-central1.run.app/api/status

## What it does
Fintelligence identifies waste in Gemini-powered financial services endpoints:

- **Fraud detection** — Using Gemini Pro for simple tasks Flash handles equally well
- **Loan eligibility** — Same 5,000-token system prompt repeated every call (cacheable)  
- **Wealth summaries** — max_output_tokens set to 4,096 but actual usage ~120 tokens

In our live deployment, Fintelligence identified **$362.78/month** ($4,353/year) 
in AI spend waste using real Dynatrace MCP data and Gemini 2.5 Flash classification.

## Tech Stack
- **Google ADK** — Agent orchestration (code-first path)
- **Gemini 2.5 Flash** via Vertex AI — Semantic request classification
- **Dynatrace MCP** — Runtime observability (18 tools, real-time span data)
- **Python + Flask** — Agent core and approval UI
- **Google Cloud Run** — Hosting

## How DEMO_MODE works
The live deployment runs with `DEMO_MODE=false`:
- Dynatrace MCP is called for real span data
- Gemini 2.5 Flash classifies requests via Vertex AI
- All classification results are genuine AI reasoning

## Setup
```bash
git clone https://github.com/monikakumarinbox-glitch/fintelligence.git
cd fintelligence

pip install flask google-cloud-aiplatform google-adk google-genai \
    requests tenacity python-dotenv opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-http mcp

export DEMO_MODE=false
export DT_ENDPOINT=https://YOUR_ENV.live.dynatrace.com
export DT_API_TOKEN=your_api_token
export DT_PLATFORM_TOKEN=your_platform_token
export GCP_PROJECT_ID=your_project_id

cd ui
python app.py
```

## Deploy to Cloud Run
```bash
gcloud run deploy fintelligence \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DEMO_MODE=false,...
```

## License
MIT
