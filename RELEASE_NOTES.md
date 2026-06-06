# Release Notes

## Release - 2026-06-06

### Latest changes
- Added backend activity logging and a `/events` API endpoint for live event feeds.
- Added a frontend activity feed panel to display recent system and transcode events.
- Logged a startup system event when the application starts and the queue manager begins running.
- Improved Plex transcoder and VAAPI hardware selection support for OMV-ready deployments.
- Included new Alembic migrations for transcode command history and activity logging.

### Commit
- `b0822da` - Add activity logging, Plex transcoder startup log, and frontend event feed UI

### Notes
- The repository is currently on `main`, synced with `origin/main`.
- Changes are ready for deployment with the updated OMV Docker Compose configuration.
