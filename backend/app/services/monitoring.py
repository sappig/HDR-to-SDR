import logging
import os
from threading import Thread

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..models import Folder
from .scan_service import ScanService as CoreScanService

logger = logging.getLogger(__name__)


class MediaFileHandler(FileSystemEventHandler):
    def __init__(self, folder_id, scan_service):
        self.folder_id = folder_id
        self.scan_service = scan_service

    def on_created(self, event):
        if not event.is_directory:
            self.scan_service.process_path(event.src_path, self.folder_id)

    def on_modified(self, event):
        if not event.is_directory:
            self.scan_service.process_path(event.src_path, self.folder_id)

    def on_moved(self, event):
        if not event.is_directory:
            self.scan_service.process_path(event.dest_path, self.folder_id)


logger = logging.getLogger(__name__)


class FolderMonitor:
    def __init__(self, session_factory, queue_manager):
        self.session_factory = session_factory
        self.queue_manager = queue_manager
        self.observer = Observer()
        self.watchers = {}
        self.scan_thread = None

    def start(self):
        session = self.session_factory()
        try:
            folders = session.query(Folder).filter(Folder.enabled.is_(True)).all()
            for folder in folders:
                if not os.path.exists(folder.path):
                    logger.warning("Skipping folder because path does not exist: %s", folder.path)
                    continue
                self.watch_folder(folder)
        finally:
            session.close()

        self.observer.start()
        self.scan_thread = Thread(target=self.scan_all_folders, daemon=True)
        self.scan_thread.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=1)

    def watch_folder(self, folder):
        if folder.id in self.watchers:
            return
        if not os.path.exists(folder.path):
            logger.warning("Cannot watch missing folder path: %s", folder.path)
            return
        scan_service = CoreScanService(self.session_factory(), self.queue_manager)
        handler = MediaFileHandler(folder.id, scan_service)
        self.observer.schedule(handler, folder.path, recursive=True)
        self.watchers[folder.id] = handler

    def scan_all_folders(self):
        session = self.session_factory()
        try:
            folders = session.query(Folder).filter(Folder.enabled.is_(True)).all()
            for folder in folders:
                if not os.path.exists(folder.path):
                    logger.warning("Skipping scan for missing folder path: %s", folder.path)
                    continue
                self.scan_folder(session, folder)
        except Exception:
            logger.exception("Folder scan thread failed")
        finally:
            session.close()

    def scan_folder(self, session, folder):
        scan_service = CoreScanService(session, self.queue_manager)
        for root, dirs, files in os.walk(folder.path):
            dirs[:] = [d for d in dirs if d.lower() not in {"extras", "bonus"}]
            for file in files:
                scan_service.process_path(os.path.join(root, file), folder.id)

