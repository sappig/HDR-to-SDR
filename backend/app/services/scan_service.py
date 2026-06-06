import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Activity, Folder, MediaFile, QueueItem
from .activity_logger import log_event


HDR_MARKERS = [
    "smpte2084",
    "arib-std-b67",
    "HDR10",
    "HDR10+",
    "HLG",
    "Dolby Vision",
]

IGNORE_PATTERNS = [
    re.compile(r"sample", re.I),
    re.compile(r"trailer", re.I),
    re.compile(r"preview", re.I),
    re.compile(r"teaser", re.I),
]

TV_PATTERNS = [
    re.compile(r"(?P<show>.+?)[._ -]?(?:(?:s|season\s*)(?P<season>\d{1,2})[._ -]?(?:e|ep|episode\s*)(?P<episode>\d{1,3})|(?P<season2>\d{1,2})x(?P<episode2>\d{1,3}))", re.I),
    re.compile(r"(?P<show>.+?)[._ -]?(?P<season>\d{1,2})[._ -]?(?P<episode>\d{1,3})", re.I),
]


def normalize_title(text: str):
    text = text.lower()
    replacements = [
        r"\b(uhd|4k|2160p|1080p|720p|fhdnonhdr|nonhdr|hdr|x264|x265|hevc|h265|h264|mkv|mp4|m4v|ts)\b",
        r"\b(bluray|brrip|webrip|webdl|remux|dvdrip|hdrip|xvid|divx)\b",
        r"\b(19|20)\d{2}\b",
        r"[._\-\s]+",
    ]
    cleaned = text
    for rep in replacements:
        cleaned = re.sub(rep, " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def find_tv_episode(name: str):
    for pattern in TV_PATTERNS:
        match = pattern.search(name)
        if match:
            groups = match.groupdict()
            season = groups.get("season") or groups.get("season2")
            episode = groups.get("episode") or groups.get("episode2")
            if season and episode:
                return int(season), int(episode), normalize_title(match.group("show"))
    return None


class ScanService:
    def __init__(self, session: Session, queue_manager):
        self.session = session
        self.queue_manager = queue_manager

    def should_ignore(self, path: str):
        lower = path.lower()
        if any(pattern.search(lower) for pattern in IGNORE_PATTERNS):
            return True
        if os.path.basename(os.path.dirname(path)).lower() in {"extras", "bonus", "sample"}:
            return True
        return False

    def analyze_media_file(self, path: str):
        ext = Path(path).suffix.lower()
        if ext not in {".mkv", ".mp4", ".m4v", ".ts"}:
            return None
        if self.should_ignore(path):
            return None

        file_size = os.path.getsize(path)
        ffprobe = self.run_ffprobe(path)
        mediainfo = self.run_mediainfo(path)
        mkvtoolnix = self.run_mkvtoolnix(path)

        resolution = None
        codec = None
        bitrate = None
        audio_tracks = None
        subtitle_tracks = None

        if ffprobe:
            streams = ffprobe.get("streams") or []
            for stream in streams:
                if stream.get("codec_type") == "video" and stream.get("width") and stream.get("height"):
                    resolution = f"{stream['width']}x{stream['height']}"
                    codec = stream.get("codec_name")
                    bitrate = stream.get("bit_rate")
                elif stream.get("codec_type") == "audio":
                    audio_tracks = (audio_tracks or 0) + 1
                elif stream.get("codec_type") == "subtitle":
                    subtitle_tracks = (subtitle_tracks or 0) + 1

        hdr_detected = False
        ffprobe_hdr_types = []
        mediainfo_hdr_types = []
        mkv_hdr_types = []

        if ffprobe:
            for stream in ffprobe.get("streams") or []:
                color_transfer = stream.get("color_transfer")
                if color_transfer in {"smpte2084", "arib-std-b67"}:
                    hdr_detected = True
                    ffprobe_hdr_types.append(color_transfer)
                if "HDR10" in str(stream.get("tags") or {}) or "Dolby Vision" in str(stream.get("tags") or {}):
                    hdr_detected = True
                    ffprobe_hdr_types.append(str(stream.get("tags")))

        if mediainfo:
            media_info = mediainfo.get("media")
            if media_info:
                for track in media_info.get("track") or []:
                    if track.get("@type") == "Video":
                        if track.get("HDR_Format") or track.get("HDR_Format_Compatibility"):
                            hdr_detected = True
                            mediainfo_hdr_types.append(track.get("HDR_Format") or track.get("HDR_Format_Compatibility"))

        if mkvtoolnix:
            output = mkvtoolnix
            if isinstance(output, str):
                for marker in HDR_MARKERS:
                    if marker in output:
                        hdr_detected = True
                        mkv_hdr_types.append(marker)

        selected_hdr_type = None
        if ffprobe_hdr_types:
            selected_hdr_type = ffprobe_hdr_types[0]
        elif mediainfo_hdr_types:
            selected_hdr_type = mediainfo_hdr_types[0]
        elif mkv_hdr_types:
            selected_hdr_type = mkv_hdr_types[0]
        output_path = self.build_output_path(path)

        return {
            "path": path,
            "filename": os.path.basename(path),
            "file_size": file_size,
            "resolution": resolution,
            "codec": codec,
            "bitrate": int(bitrate) if bitrate else None,
            "audio_tracks": audio_tracks,
            "subtitle_tracks": subtitle_tracks,
            "hdr_detected": hdr_detected,
            "hdr_type": selected_hdr_type,
            "output_path": output_path,
        }

    def run_ffprobe(self, path):
        try:
            result = subprocess.run([
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=index,codec_type,codec_name,width,height,bit_rate,color_transfer,tags",
                "-of", "json",
                path,
            ], capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            return None
        return None

    def run_mediainfo(self, path):
        try:
            result = subprocess.run(["mediainfo", "--Output=JSON", path], capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            return None
        return None

    def run_mkvtoolnix(self, path):
        try:
            result = subprocess.run(["mkvinfo", "--no-header", path], capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return result.stdout
        except Exception:
            return None
        return None

    def build_output_path(self, path):
        stem = Path(path).stem
        suffix = Path(path).suffix
        if stem.endswith(".FHDNONHDR"):
            return path
        return str(Path(path).with_name(f"{stem}.FHDNONHDR{suffix}"))

    def match_existing_sdr(self, media_data):
        folder = Path(media_data["path"]).parent
        basename = Path(media_data["path"]).stem
        normalized = normalize_title(basename)

        tv_match = find_tv_episode(basename)
        if tv_match:
            season, episode, show = tv_match
            for candidate in folder.iterdir():
                candidate_name = candidate.stem
                candidate_match = find_tv_episode(candidate_name)
                if not candidate_match:
                    continue
                candidate_season, candidate_episode, candidate_show = candidate_match
                if candidate_show == show and candidate_season == season and candidate_episode == episode:
                    candidate_normalized = normalize_title(candidate_name)
                    if "nonhdr" in candidate_normalized or "fhdnonhdr" in candidate_normalized or "1080p" in candidate_normalized:
                        return str(candidate)
            return None

        for candidate in folder.iterdir():
            candidate_name = candidate.stem
            if candidate == Path(media_data["path"]):
                continue
            if candidate.suffix.lower() not in {".mkv", ".mp4", ".m4v", ".ts"}:
                continue
            normalized_candidate = normalize_title(candidate_name)
            if normalized_candidate and normalized in normalized_candidate:
                if any(tag in normalized_candidate for tag in ["nonhdr", "fhdnonhdr", "1080p"]):
                    return str(candidate)
        return None

    def process_path(self, path, folder_id):
        media_data = self.analyze_media_file(path)
        if not media_data:
            return None
        media_file = self.upsert_media_file(folder_id, media_data)
        self.queue_if_needed(media_file)
        log_event(self.session, media_file.id, "scan", f"Discovered file {media_file.filename}, HDR={media_file.hdr_detected}, type={media_file.hdr_type or 'unknown'}")
        return media_file

    def upsert_media_file(self, folder_id, media_data):
        existing = self.session.query(MediaFile).filter_by(path=media_data["path"]).first()
        if existing:
            existing.folder_id = folder_id
            existing.filename = media_data["filename"]
            existing.file_size = media_data["file_size"]
            existing.resolution = media_data["resolution"]
            existing.codec = media_data["codec"]
            existing.bitrate = media_data["bitrate"]
            existing.audio_tracks = media_data["audio_tracks"]
            existing.subtitle_tracks = media_data["subtitle_tracks"]
            existing.hdr_detected = media_data["hdr_detected"]
            existing.hdr_type = media_data["hdr_type"]
            existing.scanned_at = datetime.utcnow()
            existing.status = "Discovered"
            existing.scan_error = None
            existing.output_path = media_data["output_path"]
            existing.extra_metadata = json.dumps(media_data)
            self.session.commit()
            return existing

        media_file = MediaFile(
            folder_id=folder_id,
            path=media_data["path"],
            filename=media_data["filename"],
            file_size=media_data["file_size"],
            resolution=media_data["resolution"],
            codec=media_data["codec"],
            bitrate=media_data["bitrate"],
            audio_tracks=media_data["audio_tracks"],
            subtitle_tracks=media_data["subtitle_tracks"],
            hdr_detected=media_data["hdr_detected"],
            hdr_type=media_data["hdr_type"],
            scanned_at=datetime.utcnow(),
            status="Discovered",
            output_path=media_data["output_path"],
            extra_metadata=json.dumps(media_data),
        )
        self.session.add(media_file)
        self.session.commit()
        self.session.refresh(media_file)
        return media_file

    def queue_if_needed(self, media_file: MediaFile):
        if not media_file.hdr_detected:
            media_file.status = "Skipped"
            self.session.commit()
            log_event(self.session, media_file.id, "scan", f"Skipped {media_file.filename}: HDR not detected")
            return

        counterpart = self.match_existing_sdr({
            "path": media_file.path,
            "filename": media_file.filename,
            "resolution": media_file.resolution,
            "codec": media_file.codec,
            "bitrate": media_file.bitrate,
            "audio_tracks": media_file.audio_tracks,
            "subtitle_tracks": media_file.subtitle_tracks,
            "hdr_detected": media_file.hdr_detected,
            "hdr_type": media_file.hdr_type,
            "output_path": media_file.output_path,
        })

        if counterpart:
            media_file.status = "Skipped"
            self.session.commit()
            log_event(self.session, media_file.id, "scan", f"Skipped {media_file.filename}: existing SDR file found")
            return

        existing_queue = self.session.query(QueueItem).filter_by(media_file_id=media_file.id).first()
        if existing_queue:
            return

        max_order = self.session.query(QueueItem.sort_order).order_by(QueueItem.sort_order.desc()).first()
        next_order = (max_order[0] if max_order else -1) + 1
        queue_item = QueueItem(
            media_file_id=media_file.id,
            priority=0,
            sort_order=next_order,
            state="Pending",
            progress=0,
            paused=False,
        )
        self.session.add(queue_item)
        media_file.status = "Queued"
        self.session.commit()
        log_event(self.session, media_file.id, "queue", f"Queued {media_file.filename} for transcoding")
