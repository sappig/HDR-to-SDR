# OMV8 Deployment Guide

This guide covers deploying the HDR-to-SDR transcoding manager on OpenMediaVault 8 with Intel Quick Sync (QSV) hardware acceleration.

## Prerequisites

- OMV8 with Docker and Docker Compose installed
- Intel-based CPU with Quick Sync support (iGPU or dedicated GPU with QSV)
- Appropriate Intel media drivers installed on the OMV host
- At least 20GB free disk space for database, logs, and temporary transcode files

## Quick Start

### 1. Prepare directories on OMV

SSH into your OMV host and create the necessary directories:

```bash
sudo mkdir -p /srv/transcode/data
sudo mkdir -p /mnt/movies
sudo mkdir -p /mnt/tv
sudo mkdir -p /srv/plex-transcoder
sudo chmod 755 /srv/transcode /srv/plex-transcoder
```

### 2. Get the compose file

```bash
cd /srv/transcode
curl -fsSL https://raw.githubusercontent.com/sappig/HDR-to-SDR/main/docker-compose.omv.yml -o docker-compose.yml
```

Edit `docker-compose.yml` and update:
- Media paths (`/mnt/movies`, `/mnt/tv`) to match your OMV setup
- Environment variables (bitrate, resolution, scan interval) as needed

### 3. Verify Intel QSV support

Before starting the container, verify your OMV host has Intel QSV available:

```bash
# Check for Intel iGPU/GPU
lspci | grep -i intel

# Check for /dev/dri devices
ls -la /dev/dri/

# Verify vainfo (Intel VA-API) if installed
which vainfo
```

If `vainfo` shows `libva2` and Intel driver support, you're good to deploy.

---

## Optional: Using Plex Transcoder Binaries

The application can use either:

1. **System ffmpeg** (default, open-source, no license restrictions)
2. **Plex Media Server transcoder** (proprietary, may have higher quality or special features)

### Option A: Use system ffmpeg (recommended for simplicity)

Leave `PLEX_TRANSCODER_PATH` empty or unset in the compose file. The app will automatically use `ffmpeg` from the base image.

### Option B: Use Plex Media Server transcoder

#### Step 1: Obtain the Plex transcoder binary

You need the Plex Media Server transcoder, which comes with Plex Media Server. There are two ways to get it:

**Method 1: Extract from installed Plex Media Server**

If you have Plex Media Server already running on your OMV or another Linux box:

```bash
# On the host with Plex installed
find / -name "PlexTranscoder" -type f 2>/dev/null
# Typically at: /usr/lib/plexmediaserver/Resources/Transcode/plex_transcoder
```

**Method 2: Download Plex Media Server (requires PMS account)**

1. Go to [plex.tv/downloads](https://plex.tv/downloads)
2. Download the Plex Media Server for your Linux distribution (Ubuntu/Debian for OMV)
3. Extract or mount the package:

```bash
# Example for .deb file
ar x plexmediaserver_*.deb
tar -xzf data.tar.gz
```

#### Step 2: Copy Plex transcoder to OMV

Transfer the Plex transcoder binary to `/srv/plex-transcoder`:

```bash
# If extracting on OMV:
mkdir -p /srv/plex-transcoder
cp /path/to/PlexTranscoder /srv/plex-transcoder/
chmod +x /srv/plex-transcoder/PlexTranscoder

# Verify it works:
/srv/plex-transcoder/PlexTranscoder -version
```

#### Step 3: Update the compose file

In `docker-compose.yml`, set:

```yaml
environment:
  - PLEX_TRANSCODER_PATH=/opt/plex-transcoder/PlexTranscoder
```

The volume mount already maps `/srv/plex-transcoder` on the host to `/opt/plex-transcoder` in the container.

---

## Deploy to OMV

### Step 1: Build the hardware-enabled image (if not using GHCR)

If you're publishing a custom image or building locally with hardware drivers:

```bash
# On OMV or a self-hosted runner that matches your distro
docker build --build-arg USE_HW=true -t ghcr.io/sappig/HDR-to-SDR:hw -f Dockerfile .
docker login ghcr.io
docker push ghcr.io/sappig/HDR-to-SDR:hw
```

Or use the pre-built image from GHCR:

```bash
# The compose file already references ghcr.io/sappig/HDR-to-SDR:hw
# This pulls the latest hardware-enabled image
```

### Step 2: Start the application

From the directory with `docker-compose.yml`:

```bash
docker compose up -d
```

Verify it's running:

```bash
docker compose ps
docker compose logs -f hdr-transcode-manager
```

### Step 3: Access the web interface

Open your browser and go to:

```
http://YOUR_OMV_IP:8080
```

You should see the dashboard with folder management, queue, and settings.

---

## Configuration

### Add monitored folders

1. Open the dashboard at `http://YOUR_OMV_IP:8080`
2. Go to **Folders** tab
3. Click **Add folder** and specify the path (e.g., `/media/movies`)
4. The app will immediately start scanning for HDR files

### Adjust settings

Go to **Settings** to configure:
- **Output Bitrate**: 4500 kbps (good quality) to 8000 kbps (high quality)
- **Output Resolution**: 1920x1080 (FHD) or lower for older devices
- **Max concurrent transcodes**: 1–4 depending on your CPU
- **Scan interval**: How often folders are scanned for new files

### Queue management

- Files detected as HDR are automatically added to the queue
- The **Queue** tab shows pending and in-progress transcodes
- Pause/resume/remove individual jobs as needed

---

## Monitoring Intel QSV usage

To verify that QSV is being used during transcoding:

```bash
# Inside the running container
docker exec hdr-transcode-manager bash -c "watch -n1 'ps aux | grep -i transcode'"

# Or check GPU utilization on the host
# (requires intel-gpu-tools or similar)
```

---

## Troubleshooting

### Issue: "Cannot find /dev/dri"

- Ensure `/dev/dri` exists on the host: `ls -la /dev/dri/`
- If missing, Intel QSV support may not be available; fall back to software encoding.

### Issue: "PlexTranscoder not found"

- Check that `/srv/plex-transcoder/PlexTranscoder` exists on the host
- Verify permissions: `ls -la /srv/plex-transcoder/`
- Leave `PLEX_TRANSCODER_PATH` unset to use ffmpeg instead

### Issue: Slow transcode or frequent CPU usage spikes

- Reduce `MAX_CONCURRENT_TRANSCODES` to 1 or 2
- Verify `/dev/dri` is mounted and accessible inside the container
- Check `docker compose logs` for errors

### Issue: Container fails to start

- Run `docker compose logs hdr-transcode-manager` to see the error
- Ensure all volume paths exist and have proper permissions
- Verify the image exists: `docker image ls | grep hdr-transcode`

---

## Updating

To pull the latest image and restart:

```bash
docker compose pull
docker compose up -d
```

Or rebuild locally:

```bash
docker compose up -d --build
```

---

## Persistence

The application stores state in SQLite at `/data/transcode.db` (mounted to `/srv/transcode/data` on the host). This persists across restarts, so your queue and settings are preserved.

Logs are also stored in `/data/` for troubleshooting.
