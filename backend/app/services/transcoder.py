import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field


@dataclass
class TranscodeResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    output_path: str = ""


class TranscoderRunner:
    def __init__(self, settings_provider):
        self.settings_provider = settings_provider

    def get_setting(self, key, default=None):
        if callable(self.settings_provider):
            return self.settings_provider(key, default)
        if hasattr(self.settings_provider, "get"):
            return self.settings_provider.get(key, default)
        return default

    def discover_plex_transcoder(self):
        override = self.get_setting("plex_transcoder_path")
        candidates = []
        if override:
            candidates.append(override)
        candidates.extend([
            "/usr/lib/plexmediaserver/Plex Transcoder",
            "/usr/lib/plexmediaserver/PlexTranscoder",
            "/usr/lib/plexmediaserver/Resources/Plex Transcoder",
            "/usr/local/bin/plex-transcoder",
            "/usr/bin/ffmpeg",
        ])
        for candidate in candidates:
            if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return shutil.which("ffmpeg")

    def get_version(self, binary_path):
        try:
            proc = subprocess.run([binary_path, "-version"], capture_output=True, text=True, timeout=20)
            output = (proc.stdout or proc.stderr or "").splitlines()
            return output[0] if output else None
        except Exception:
            return None

    def detect_qsv(self):
        # Prefer VA-API detection via vainfo, then fall back to ffmpeg hwaccels
        if shutil.which("vainfo"):
            try:
                proc = subprocess.run(["vainfo"], capture_output=True, text=True, timeout=20)
                if proc.returncode == 0 and "Intel" in (proc.stdout + proc.stderr):
                    return True
            except Exception:
                pass

        if shutil.which("ffmpeg"):
            try:
                proc = subprocess.run(["ffmpeg", "-hide_banner", "-hwaccels"], capture_output=True, text=True, timeout=20)
                if proc.returncode == 0 and "qsv" in (proc.stdout + proc.stderr).lower():
                    return True
            except Exception:
                pass

        return os.path.exists("/dev/dri")

    def build_command(self, input_path, output_path, width=1920, height=1080, bitrate=4500, software_fallback=False):
        binary = self.discover_plex_transcoder()
        if not binary:
            raise RuntimeError("No transcoder binary found")

        fallback = software_fallback or os.path.basename(binary) == "ffmpeg"

        if fallback:
            command = [
                binary,
                "-y",
                "-hwaccel", "auto",
                "-i", input_path,
                "-map", "0:v:0",
                "-map", "0:a?",
                "-map", "0:s?",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-vf", f"scale={width}:{height}:flags=lanczos,format=yuv420p",
                "-b:v", f"{bitrate}k",
                "-preset", "medium",
                "-movflags", "+faststart",
                "-c:a", "aac",
                "-ac", "2",
                "-c:s", "copy",
                output_path,
            ]
        else:
            command = [
                binary,
                "-i", input_path,
                "-map", "0:v:0",
                "-map", "0:a?",
                "-map", "0:s?",
                "-c:v", "h264_qsv",
                "-preset", "medium",
                "-profile:v", "high",
                "-vf", "scale_qsv=iw:ih,format=nv12,hwupload=1,scale_qsv=1920:1080",
                "-b:v", f"{bitrate}k",
                "-c:a", "aac",
                "-ac", "2",
                "-c:s", "copy",
                output_path,
            ]
        return command

    def transcode(self, input_path, output_path, bitrate=4500, width=1920, height=1080, software_fallback=False):
        command = self.build_command(input_path, output_path, width, height, bitrate, software_fallback)
        start = time.time()
        proc = subprocess.run(command, capture_output=True, text=True)
        duration = max(1, int(time.time() - start))
        return TranscodeResult(
            success=proc.returncode == 0 and os.path.exists(output_path),
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
            output_path=output_path,
        )
