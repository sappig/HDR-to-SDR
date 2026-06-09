import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import MediaFile, QueueItem, TranscodeHistory
from .activity_logger import log_event
from .transcoder import TranscoderRunner

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.runner = None
        self._running = True

    def stop(self):
        self._running = False

    def build_runner(self, session: Session):
        settings = self.load_settings(session)
        self.runner = TranscoderRunner(settings)
        return self.runner

    def load_settings(self, session: Session):
        data = {}
        from ..models import AppSetting

        for row in session.query(AppSetting).all():
            data[row.key] = row.value
        return data

    def build_temp_output_path(self, output_path: str) -> str:
        return f"{output_path}.part"

    def cleanup_incomplete_output(self, output_path: str):
        temp_output = self.build_temp_output_path(output_path)
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass

    def estimate_eta(self, media_file_size: int, bitrate: int) -> int:
        if not media_file_size or not bitrate:
            return 0
        # Roughly estimate based on target bitrate and file size.
        # This is only a heuristic; actual time depends on hardware and source complexity.
        seconds = int(media_file_size / (bitrate * 125) * 1.5)
        return max(30, seconds)

    async def run(self):
        while self._running:
            try:
                await asyncio.to_thread(self.process_cycle)
            except Exception:
                logger.exception("Queue manager cycle failed")
            await asyncio.sleep(2)

    def process_cycle(self):
        session = self.session_factory()
        try:
            recovering = session.query(QueueItem).filter(QueueItem.state.in_(["Scanning", "Transcoding"])).all()
            for item in recovering:
                item.state = "Pending"
                item.progress = 0
                item.started_at = None
                item.completed_at = None
                item.eta_seconds = None
                media_file = session.query(MediaFile).filter(MediaFile.id == item.media_file_id).first()
                if media_file and media_file.output_path:
                    self.cleanup_incomplete_output(media_file.output_path)
            session.commit()
            self.process_queue(session)
        finally:
            session.close()

    def process_queue(self, session: Session):
        active = session.query(QueueItem).filter(QueueItem.state.in_(["Pending", "Waiting"])).order_by(QueueItem.sort_order.asc()).all()
        for item in active:
            if item.paused:
                item.state = "Waiting"
                session.commit()
                continue
            media_file = session.query(MediaFile).filter_by(id=item.media_file_id).first()
            if not media_file:
                continue
            if not os.path.exists(media_file.path):
                item.state = "Failed"
                item.last_error = "Source file missing"
                session.commit()
                log_event(session, media_file.id, "transcode", f"Transcode failed: source missing for {media_file.filename}")
                continue

            item.state = "Scanning"
            item.progress = 5
            session.commit()

            output_path = media_file.output_path or self.build_output_path(media_file.path)
            temp_output_path = self.build_temp_output_path(output_path)
            if os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except OSError:
                    pass

            if os.path.exists(output_path):
                media_file.status = "Skipped"
                item.state = "Completed"
                item.progress = 100
                item.completed_at = datetime.utcnow()
                item.eta_seconds = 0
                session.commit()
                continue

            item.state = "Transcoding"
            item.progress = 10
            item.started_at = datetime.utcnow()
            session.commit()

            settings = self.load_settings(session)
            runner = self.build_runner(session)
            qsv_available = runner.detect_qsv()
            software_fallback = str(settings.get("software_fallback", "false")).lower() == "true"
            if not qsv_available and not software_fallback:
                item.state = "Failed"
                item.progress = 100
                item.eta_seconds = 0
                item.last_error = "QSV not available and software fallback disabled"
                item.completed_at = datetime.utcnow()
                media_file.status = "Failed"
                session.commit()
                log_event(session, media_file.id, "transcode", f"Transcode failed: QSV unavailable for {media_file.filename}")
                continue

            item.eta_seconds = self.estimate_eta(media_file.file_size, int(settings.get("output_bitrate", 4500)))
            session.commit()

            log_event(session, media_file.id, "transcode", f"Starting transcoding {media_file.filename}")
            result = runner.transcode(
                media_file.path,
                temp_output_path,
                bitrate=int(settings.get("output_bitrate", 4500)),
                width=int(settings.get("output_resolution", "1920x1080").split("x")[0]),
                height=int(settings.get("output_resolution", "1920x1080").split("x")[1]),
                software_fallback=software_fallback and not qsv_available,
            )

            history = TranscodeHistory(
                media_file_id=media_file.id,
                started_at=item.started_at,
                completed_at=datetime.utcnow(),
                result="success" if result.success else "failed",
                log=(result.stdout or "") + (result.stderr or ""),
            )
            session.add(history)
            item.transcode_command = result.command

            if result.success:
                if temp_output_path != output_path and os.path.exists(temp_output_path):
                    os.replace(temp_output_path, output_path)
                item.state = "Completed"
                item.progress = 100
                item.completed_at = datetime.utcnow()
                item.eta_seconds = 0
                media_file.status = "Completed"
                media_file.output_path = output_path
                session.commit()
                log_event(session, media_file.id, "transcode", f"Transcoding successful for {media_file.filename}")
            else:
                if os.path.exists(temp_output_path):
                    try:
                        os.remove(temp_output_path)
                    except OSError:
                        pass
                item.state = "Failed"
                item.progress = 100
                item.eta_seconds = 0
                item.last_error = (result.stderr or result.stdout or "Transcoding failed")[:1000]
                media_file.status = "Failed"
                session.commit()
                log_event(session, media_file.id, "transcode", f"Transcoding failed for {media_file.filename}: {item.last_error}")

    def build_output_path(self, path):
        from pathlib import Path

        output_path = Path(path)
        if output_path.stem.endswith(".FHDNONHDR"):
            return str(output_path)
        return str(output_path.with_name(f"{output_path.stem}.FHDNONHDR{output_path.suffix}"))
