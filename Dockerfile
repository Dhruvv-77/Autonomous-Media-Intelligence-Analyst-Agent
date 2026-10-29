# ==============================================================================
# Autonomous Media Intelligence Analyst Agent — Production Container
# ==============================================================================

# Stage 1: Build React Frontend Assets
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit || npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend & Fast Server
FROM python:3.11-slim
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code, configuration, and benchmark datasets
COPY src/ ./src/
COPY data/ ./data/
COPY mock_crm/ ./mock_crm/
COPY config.yaml .
COPY run.py .

# Copy compiled frontend distribution from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure writable outputs directory exists
RUN mkdir -p outputs

# Cloud hosting port configuration
ENV PORT=8000
ENV HOST=0.0.0.0
EXPOSE 8000

# Start unified FastAPI server + React dashboard
CMD ["python", "run.py"]
