# ==========================================
# ResQGrid Multi-Stage Production Dockerfile
# ==========================================

# Stage 1: Build the React + Vite Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend & Unified Server
FROM python:3.11-slim AS production
WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install backend requirements
COPY backend_py/requirements.txt ./backend_py/
RUN pip install --no-cache-dir -r ./backend_py/requirements.txt

# Copy backend application code & data
COPY backend_py/ ./backend_py/

# Copy compiled frontend from Stage 1 into /app/frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Set working directory to backend_py
WORKDIR /app/backend_py

# Port configuration
ENV PORT=8000
EXPOSE 8000

# Start Uvicorn production server
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
