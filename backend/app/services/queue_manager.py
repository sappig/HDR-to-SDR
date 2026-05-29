import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import MediaFile, QueueItem, TranscodeHistory
from .transcoder import TranscoderRunner


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

    async def run(self):
        while True:
            session = self.session_factory()
            try:
                recovering = session.query(QueueItem).filter(QueueItem.state.in_(["Scanning", "Transcoding"])).all()
                for item in recovering:
                    item.state = "Pending"
                    item.progress = 0
                    item.started_at = None
                    item.completed_at = None
                session.commit()
                self.process_queue(session)
            finally:
                session.close()
            await asyncio.sleep(2)

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
                continue

            item.state = "Scanning"
            item.progress = 5
            session.commit()

            output_path = media_file.output_path or self.build_output_path(media_file.path)
            if os.path.exists(output_path):
                media_file.status = "Skipped"
                item.state = "Completed"
                item.progress = 100
                item.completed_at = datetime.utcnow()
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
                item.last_error = "QSV not available and software fallback disabled"
                item.completed_at = datetime.utcnow()
                media_file.status = "Failed"
                session.commit()
                continue

            result = runner.transcode(
                media_file.path,
                output_path,
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

            if result.success:
                item.state = "Completed"
                item.progress = 100
                item.completed_at = datetime.utcnow()
                media_file.status = "Completed"
                media_file.output_path = output_path
                session.commit()
            else:
                item.state = "Failed"
                item.progress = 100
                item.completed_at = datetime.utcnow()
                item.last_error = (result.stderr or result.stdout or "Transcoding failed")[:1000]
                media_file.status = "Failed"
                session.commit()

    def build_output_path(self, path):
        from pathlib import Path

        output_path = Path(path)
        if output_path.stem.endswith(".FHDNONHDR"):
            return str(output_path)
        return str(output_path.with_name(f"{output_path.stem}.FHDNONHDR{output_path.suffix}"))
