# Database Backup and Restore Guide

This guide covers backing up and restoring LAN Paste's SQLite database stored in the Docker volume.

## Volume and Database Files

LAN Paste persists data in the named Docker volume `paste-data` mounted at `/data` inside the `app` container.

SQLite operates in Write-Ahead Logging (`WAL`) mode (`PRAGMA journal_mode=WAL`), which uses up to three files:

| File | Purpose |
|------|---------|
| `pastes.db` | Main SQLite database file |
| `pastes.db-wal` | Write-Ahead Log file (uncheckpointed transactions) |
| `pastes.db-shm` | Shared memory index for WAL concurrency |

> [!IMPORTANT]
> Always back up and restore all three files (`pastes.db*`) together. Omitting the WAL file while transactions are uncheckpointed can result in data loss or database corruption.

---

## `docker compose down` vs `docker compose down -v`

| Command | Effect on `paste-data` Volume |
|---------|--------------------------------|
| `docker compose down` | **Preserves** the volume and all pastes. Safe for routine stops and updates. |
| `docker compose down -v` | **DELETES** the volume and all pastes permanently. **Irreversible data loss.** |

---

## Cold Backup Procedure (Recommended)

A cold backup provides a consistent, atomic snapshot by stopping the service first:

1. **Stop the application container:**
   ```sh
   docker compose stop app
   ```

2. **Copy database files from the volume to a host backup directory:**
   ```sh
   BACKUP_DIR="./backups/$(date +%F_%H-%M-%S)"
   mkdir -p "$BACKUP_DIR"

   docker run --rm \
     -v lan-paste_paste-data:/source:ro \
     -v "$(pwd)/$BACKUP_DIR":/dest \
     alpine cp -a /source/pastes.db* /dest/
   ```

   *(Note: Adjust `lan-paste_paste-data` if your Compose project prefix differs; check with `docker volume ls`)*

3. **Restart the application:**
   ```sh
   docker compose start app
   ```

4. **Verify the backup files:**
   ```sh
   ls -la "$BACKUP_DIR"
   ```

---

## Restore Procedure

1. **Stop the application:**
   ```sh
   docker compose stop app
   ```

2. **Remove current database files from the volume:**
   ```sh
   docker run --rm \
     -v lan-paste_paste-data:/dest \
     alpine rm -f /dest/pastes.db*
   ```

3. **Copy the backup files into the volume:**
   ```sh
   BACKUP_DIR="./backups/2026-10-24_12-00-00"

   docker run --rm \
     -v "$(pwd)/$BACKUP_DIR":/source:ro \
     -v lan-paste_paste-data:/dest \
     alpine cp -a /source/pastes.db* /dest/
   ```

4. **Start the application:**
   ```sh
   docker compose start app
   ```

5. **Validate restored data:**
   - **Via API:**
     ```sh
     curl -fsS http://localhost:8000/api/pastes
     ```
   - **Via Browser:** Open `http://HOST-LAN-IP:8000` and confirm recent pastes are visible.
   - **Check logs:**
     ```sh
     docker compose logs --tail=20 app
     ```

---

## WAL and SHM Safety Notes

- Never manually delete `pastes.db-wal` or `pastes.db-shm` while the container is running.
- When copying files while the container is stopped, SQLite automatically recovers and replays the WAL log when the service restarts.
- Do not commit backup files or database snapshots into Git repositories.
