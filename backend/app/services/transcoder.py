import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TranscodeResult:
    success: bool
    command: str = ""
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
        if override and os.path.exists(override) and os.access(override, os.X_OK):
            return override

        candidates = [
            "/usr/lib/plexmediaserver/Plex Transcoder",
            "/usr/lib/plexmediaserver/PlexTranscoder",
            "/usr/lib/plexmediaserver/Resources/Plex Transcoder",
            "/opt/plex-transcoder/PlexTranscoder",
            "/usr/local/bin/plex-transcoder",
            "/usr/bin/ffmpeg",
        ]
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
        # Detect available hardware acceleration support, including VA-API and QSV.
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
                if proc.returncode == 0:
                    hwaccels = (proc.stdout + proc.stderr).lower()
                    if "vaapi" in hwaccels or "qsv" in hwaccels:
                        return True
            except Exception:
                pass

        return os.path.exists("/dev/dri")

    def build_command(self, input_path, output_path, width=1920, height=1080, bitrate=4500, software_fallback=False):
        binary = self.discover_plex_transcoder()
        if not binary:
            raise RuntimeError("No transcoder binary found")

        use_software = software_fallback or not self.detect_qsv()
        output_ext = Path(output_path).suffix.lower()
        subtitle_codec = "mov_text" if output_ext in {".mp4", ".m4v", ".mov"} else "copy"

        if use_software:
            command = [
                binary,
                "-y",
                "-analyzeduration", "20000000",
                "-probesize", "20000000",
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
                "-b:a", "192k",
                "-c:s", subtitle_codec,
                output_path,
            ]
        else:
            command = [
                binary,
                "-y",
                "-hide_banner",
                "-nostats",
                "-loglevel", "quiet",
                "-analyzeduration", "20000000",
                "-probesize", "20000000",
                "-hwaccel", "vaapi",
                "-hwaccel_device", "/dev/dri/renderD128",
                "-hwaccel_output_format", "vaapi",
                "-init_hw_device", "vaapi=vaapi:/dev/dri/renderD128,driver=iHD",
                "-filter_hw_device", "vaapi",
                "-i", input_path,
                "-filter_complex",
                (
                    f"[0:v]hwupload,scale_vaapi=w={width}:h={height}:format=p010[1];"
                    "[1]hwmap=derive_device=opencl[2];"
                    "[2]tonemap_opencl=tonemap=hable:format=nv12:m=bt709:p=bt709:r=tv[3];"
                    "[3]hwmap=derive_device=vaapi:reverse=1[4];"
                    "[4]hwupload[5]"
                ),
                "-map", "[5]",
                "-map", "0:a?",
                "-map", "0:s?",
                "-c:v", "h264_vaapi",
                "-b:v", f"{bitrate}k",
                "-maxrate", f"{bitrate * 2}k",
                "-bufsize", f"{bitrate * 4}k",
                "-r", "23.976",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-c:a", "aac",
                "-ac", "2",
                "-b:a", "192k",
                "-c:s", subtitle_codec,
                "-map_metadata", "-1",
                "-map_chapters", "-1",
                output_path,
            ]
        return command

    def transcode(self, input_path, output_path, bitrate=4500, width=1920, height=1080, software_fallback=False, progress_callback=None):
        command = self.build_command(input_path, output_path, width, height, bitrate, software_fallback)
        command_text = " ".join(command)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stdout_lines = []
        stderr_lines = []

        if proc.stderr:
            for line in proc.stderr:
                stderr_lines.append(line)
                if progress_callback:
                    progress_callback(line)

        if proc.stdout:
            stdout_output, _ = proc.communicate(timeout=10)
            stdout_lines.append(stdout_output)
        else:
            proc.communicate()

        returncode = proc.returncode
        success = returncode == 0 and os.path.exists(output_path)

        return TranscodeResult(
            command=command_text,
            success=success,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
            returncode=returncode,
            output_path=output_path,
        )
