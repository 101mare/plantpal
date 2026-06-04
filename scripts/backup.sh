#!/usr/bin/env bash
# PlantPal daily backup (K5): WAL-consistent SQLite snapshot + rsync of DB and images.
# No sqlite3 CLI required — the snapshot uses sqlite3.Connection.backup via the app CLI.
#
# Install on the host crontab, e.g. daily at 03:30:
#   30 3 * * *  PLANTPAL_BACKUP_DEST=/backup/plantpal /opt/plantpal/scripts/backup.sh
set -euo pipefail

STAMP="$(date +%F)"
DEST="${PLANTPAL_BACKUP_DEST:-/backup/plantpal}"
mkdir -p "$DEST"

# 1) Consistent snapshot of the live DB inside the container's volume.
docker compose exec -T plantpal python -m plantpal.cli backup --out /data/backup.db

# 2) Copy the snapshot + images out of the volume to the backup destination.
docker compose cp plantpal:/data/backup.db "$DEST/plantpal-${STAMP}.db"
rm -rf "$DEST/images-${STAMP}"
docker compose cp plantpal:/data/images "$DEST/images-${STAMP}"

# 3) Optional: mirror to a remote (set PLANTPAL_BACKUP_RSYNC=user@host:/path).
if [[ -n "${PLANTPAL_BACKUP_RSYNC:-}" ]]; then
  rsync -az --delete "$DEST/" "$PLANTPAL_BACKUP_RSYNC/"
fi

echo "Backup done: $DEST/plantpal-${STAMP}.db (+ images-${STAMP}/)"
