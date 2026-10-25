# Troubleshooting LAN Paste

Run Compose commands from the directory containing `compose.yaml`. The commands
below use Docker Engine and the Compose plugin. Shell-specific commands are
labelled; replace `HOST-LAN-IP` with the Docker host's address.

Keep `.env`, admin tokens and paste contents private. Before sharing logs, remove
secrets and private URLs/IDs. Do not publish `docker compose config` output or a
full container environment. `docker compose config --quiet` validates configuration
without printing the expanded token.

## Port 8000 is already in use

**Symptom:** `docker compose up -d --build` reports that the port is allocated or
cannot be bound.

**Likely cause:** another process or container already publishes host TCP/8000.
Find the owner before stopping anything:

```sh
docker ps --filter publish=8000 --format 'table {{.Names}}\t{{.Ports}}'
```

For a non-Docker listener, Linux users can run `ss -ltnp 'sport = :8000'`.
On Windows, PowerShell can run:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

Stop the conflicting service only if it is yours and safe to stop. Alternatively,
change only the **host** side of the Compose mapping to `"8001:8000"`, recreate
with `docker compose up -d --build`, and use port 8001 in URLs and firewall rules.
The application still listens on container port 8000. Do not expose either port
through router port forwarding.

## The admin token is missing or unset

**Symptom:** Compose refuses to start and asks to set `PASTE_ADMIN_TOKEN`.
A directly run application without the token returns 503 for DELETE requests.

**Likely cause:** the private `.env` file is missing, the value is blank, or an
exported environment variable overrides it. Follow the README's configuration
steps to generate a fresh token and put it after `PASTE_ADMIN_TOKEN=` in `.env`.
Never use the example placeholder as the actual token.

```sh
docker compose config --quiet
docker compose up -d --build
```

The first command should exit successfully without printing the configuration.
The second recreates the container when its configuration has changed.
`docker compose restart` alone does not apply a changed environment. A 403 on a
DELETE request instead means the supplied `X-Admin-Token` does not match; do not
paste either value into a bug report.

## The container repeatedly restarts

**Symptom:** the service never stays up or requests fail after startup.

```sh
docker compose ps -a
docker compose logs --tail=100 lan-paste
```

`ps` shows whether the container exited/restarts; the logs show the startup
failure. Look for an invalid `DEFAULT_TTL_HOURS`, a SQLite error, or a volume
ownership/permission failure. In the supplied Compose file the volume is mounted
at `/data`; the Dockerfile fixes its ownership before switching to `appuser`.
Do not remove those privileges or replace the volume with an unwritable bind
mount without arranging equivalent ownership.

If the service stays up long enough, check the application user and directory
permissions without reading the database:

```sh
docker compose exec --user appuser lan-paste sh -c 'id; ls -ld /data'
```

Correct the reported configuration or mount problem, then run
`docker compose up -d --build` again. Do not delete the database or volume as a
first troubleshooting step. There is no need to print environment variables or
paste data to diagnose a startup failure.

## Another device cannot reach the service

**Symptom:** the browser cannot open `http://HOST-LAN-IP:8000`.

First check the host, using the published port (8000 unless you changed it):

```sh
docker compose ps
curl -I http://127.0.0.1:8000/
```

On Windows PowerShell, use `curl.exe` for the curl examples. An HTTP response
shows that the service is reachable locally. If this fails, resolve the container
or port problem first. If it works locally but fails from another device:

- Use the Docker **host's** LAN address, not `localhost` (which refers to the
  client device) or the container's private address. Linux: `ip -brief address`;
  Windows: `ipconfig`.
- Check that the devices share a trusted network. Guest Wi-Fi/client isolation
  may prevent device-to-device connections.
- Allow the published TCP port only on the intended LAN/Tailscale interfaces in
  the host firewall; do not disable the firewall globally.
- For Tailscale, confirm both devices are connected, use the host's Tailscale
  address, and check the tailnet access controls.

Do not add router port forwarding: this service is intended for trusted private
networks and has no per-user read/create authentication.

## A paste is missing or expired

**Symptom:** its URL returns 404, or it is absent from the recent-pastes list.

The list shows only the 50 most recent pastes, so try the original private URL.
Check the expiry chosen at creation: 1 hour, 24 hours, 7 days, or never. Expired
rows are deleted during normal requests; changing `DEFAULT_TTL_HOURS` does not
extend an already-created paste. An admin may also have deleted it.

If *all* old pastes disappeared after deployment, check that Compose is using the
same project and named volume. Changing the checkout directory, project name
(`-p`/`COMPOSE_PROJECT_NAME`), or mount can select a different, empty database.
These commands list containers and candidate volumes without reading pastes:

```sh
docker compose ps -a
docker volume ls --filter label=com.docker.compose.volume=paste_data
```

Do not attach or delete a volume just because its name looks plausible. Verify
the deployment/project and backup first. A deleted or expired paste cannot be
recovered from the service; restore a suitable backup if you have one, following
the README's [maintenance guidance](../README.md#maintenance).

## The Docker volume was accidentally removed

**Symptom:** the service starts with an empty database after a volume deletion.

`docker compose down` preserves the named volume. **`docker compose down -v`
deletes the project's named database volume and its saved pastes.** Removing the
volume manually has the same data-loss risk. Do not run either deletion command
as a repair step.

Stop the service with `docker compose stop` while locating a known-good backup
and verifying the intended project/volume. If another existing volume was merely
selected by mistake, preserve both volumes until the configuration is understood.
If the original volume was actually deleted, starting the service creates a new
empty database; restarting cannot bring the old records back. Restore from your
backup before restarting, or accept the loss if no backup exists. Never share a
database backup publicly: it contains unencrypted paste contents.
