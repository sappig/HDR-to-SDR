from fastapi import APIRouter

from ..services.transcoder import TranscoderRunner

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def system_status():
    runner = TranscoderRunner(lambda key, default=None: None)
    binary = runner.discover_plex_transcoder()
    return {
        "qsv_available": runner.detect_qsv(),
        "plex_binary": binary,
        "plex_version": runner.get_version(binary) if binary else None,
        "volume_hint": "After adding a folder, restart the container with the updated volume mapping.",
    }
