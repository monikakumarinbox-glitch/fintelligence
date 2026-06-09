FROM python:3.11-slim

WORKDIR /app

# Copy both agent and ui from project root
COPY agent/ ./agent/
COPY ui/ ./ui/

# Install dependencies
RUN pip install --no-cache-dir \
    flask \
    google-cloud-aiplatform \
    google-adk \
    google-genai \
    requests \
    tenacity \
    python-dotenv \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-http \
    mcp

# Set working directory to ui
WORKDIR /app/ui

ENV PORT=8080
EXPOSE 8080

CMD ["python", "app.py"]





