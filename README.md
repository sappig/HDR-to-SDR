# HDR to FHD Transcoding Manager

A Dockerized FastAPI + React service for detecting HDR media, queueing FHD SDR transcodes, and monitoring folders with Plex/QSV-aware transcoding.

## Features

- Recursive folder monitoring with watchdog
- HDR detection using ffprobe, MediaInfo, and MKVToolNix metadata inspection
- SDR counterpart matching for movie and TV episode naming patterns
- Persistent SQLite queue with restart recovery
- Plex transcoder discovery with manual override and QSV hardware detection
- Material UI dashboard, folder management, queue controls, and settings
- Swagger/OpenAPI docs exposed at `/docs`

## Docker

### Quick start (local development)

```bash
cp .env.example .env
docker compose up --build
```

The application listens on port `8080`.

### OMV8 deployment with Intel QSV

For OpenMediaVault 8 deployments with hardware acceleration, see [DEPLOY.md](DEPLOY.md) and use `docker-compose.omv.yml`:

```bash
curl -fsSL https://raw.githubusercontent.com/sappig/HDR-to-SDR/main/docker-compose.omv.yml -o docker-compose.yml
docker compose up -d
```

This includes:
- Intel QSV hardware acceleration via `/dev/dri`
- OMV-friendly volume mappings
- Example environment variables
- Plex transcoder integration (optional)

## Folder volume guidance

Use the generated folder mapping snippet in the UI. After adding a folder, restart the container with the updated host path mapping so the watcher can inspect the new media directory.

Example snippet:

```yaml
volumes:
  - /media/movies:/media/movies
  - /media/tv:/media/tv
```

## API

- `/folders`
- `/files`
- `/queue`
- `/settings`
- `/system/status`
- Swagger at `/docs`

## Local development

Backend:

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8080
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## GitHub Container Registry deployment

This repo includes a GitHub Actions workflow at `.github/workflows/docker-publish.yml` that builds the image and pushes it to `ghcr.io`.

Example deploy command from a fresh machine:

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/docker-compose.ghcr.yml -o docker-compose.yml
# edit docker-compose.yml and replace ghcr.io/OWNER/REPO:latest with your real image name
docker compose up -d
```

For a fixed deployment, replace `ghcr.io/OWNER/REPO:latest` with your real GHCR image name in `docker-compose.ghcr.yml`.

### Building a hardware-enabled image

If you need the image to include Intel VA / QSV drivers, build and push the image from a machine that has access to the appropriate package repositories and drivers (for example, your target OMV host or a self-hosted runner that matches your distro). Example local build and push:

```bash
# build with hardware drivers enabled
docker build --build-arg USE_HW=true -t ghcr.io/OWNER/REPO:hw -f Dockerfile .
# log in and push
docker login ghcr.io
docker push ghcr.io/OWNER/REPO:hw
```

You can then reference `ghcr.io/OWNER/REPO:hw` in your `docker-compose.yml` for hosts with compatible hardware and drivers.

## Notes

The application uses SQLite persistence in `/data/transcode.db`. Queue state and file scan results survive restarts.
