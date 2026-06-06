FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
COPY frontend/tsconfig*.json ./
COPY frontend/vite.config.ts ./
COPY frontend/index.html ./
COPY frontend/src ./src
RUN npm ci
RUN npm run build

FROM python:3.12-slim
ARG USE_HW=false
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install common packages; install Intel VA packages only when explicitly requested
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    mediainfo \
    mkvtoolnix \
    curl \
    ca-certificates \
    build-essential \
    && if [ "$USE_HW" = "true" ]; then apt-get install -y --no-install-recommends libva2 vainfo intel-media-va-driver-nonfree || true; fi \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends plexmediaserver || true

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY .env.example ./.env.example
COPY --from=frontend-builder /app/frontend/dist ./frontend_dist

RUN mkdir -p /data

EXPOSE 8080

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
