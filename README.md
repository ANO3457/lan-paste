# LAN Paste

A small self-hosted paste service for a trusted LAN or private Tailscale network. Flask serves the browser UI and a JSON/raw-body API; SQLite persists pastes in a Docker volume.

## Requirements

- Docker Engine and Docker Compose plugin
- A trusted LAN, and optionally Tailscale installed on the host and client devices

## 1. Configure

Create a private `.env` file from the example and generate a strong token:

```sh
cp .env.example .env
openssl rand -hex 32
# Put the generated value after PASTE_ADMIN_TOKEN= in .env
```

Compose refuses to start until `PASTE_ADMIN_TOKEN` is set. `.env` is ignored by Git; never commit or share it.

## 2. Build and run

```sh
docker compose up -d --build
docker compose logs -f
```

Find the host's LAN IP, then open `http://HOST-LAN-IP:8000`. On a Linux host, `ip -brief address` can help identify the LAN interface and address. Use the host's Tailscale IP to connect from your own Tailscale devices, for example `http://TAILSCALE-IP:8000`.

The port is reachable only where network routes and firewall rules allow it. Do not configure router port forwarding. Restrict TCP/8000 to your LAN and Tailscale interfaces using your host firewall. Tailscale access controls can further limit which devices can connect.

## Browser features

- Create pastes with an optional title
- Choose expiry after 1 hour, 24 hours, 7 days, or never
- Open a paste by its unique URL and copy its content
- View the 50 most recent pastes
- Expired pastes are removed during normal requests

## Quick-paste API

Paste stdin (or a file) and receive JSON containing the paste URL:

```sh
printf 'hello from terminal\n' | curl -fsS http://HOST-LAN-IP:8000/api/pastes \\
  -H 'X-Paste-Title: terminal note' \\
  --data-binary @-
```

Paste a file:

```sh
curl -fsS http://HOST-LAN-IP:8000/api/pastes \\
  -H 'X-Paste-Title: config snippet' \\
  --data-binary @./config.yaml
```

Set expiry using `X-Paste-TTL: 1`, `24`, `168`, or `never`. Omit it to use `DEFAULT_TTL_HOURS`.

JSON clients can send `{"title":"note","content":"hello","ttl_hours":24}` with `Content-Type: application/json`.

JSON bodies must be objects. `content` must be a non-empty string (not just
whitespace), and `title`, when supplied, must be a string. Explicit `null`,
numbers, arrays, and objects are not accepted for either field. For JSON, `ttl_hours`
accepts integers `1`, `24`, `168`, their string forms, or `"never"`. Omitting it,
using `null`, `""`, or `"default"` uses `DEFAULT_TTL_HOURS`. Boolean and fractional
values are rejected. Raw-body clients keep using the title and TTL headers above.

API errors return JSON with one non-empty `error` message, for example
`{"error":"JSON body must be an object"}`. Invalid JSON, invalid fields or TTL,
empty content, and paste content over 1 MiB return `400`. Requests exceeding the
request-body limit (1 MiB plus 8 KiB of allowance for JSON) return `413`. Missing
pastes return `404`, unsupported methods return `405` with an `Allow` header,
and unexpected internal failures return a generic `500` without internal details.
Browser pages retain human-readable error responses. Successful creation still
returns `201` with the paste ID, URL, and expiry.

List recent pastes:

```sh
curl -fsS http://HOST-LAN-IP:8000/api/pastes
```

Read a paste as JSON:

```sh
curl -fsS http://HOST-LAN-IP:8000/api/pastes/PASTE_ID
```

Delete a paste (admin token required):

```sh
curl -fsS -X DELETE http://HOST-LAN-IP:8000/api/pastes/PASTE_ID \\
  -H 'X-Admin-Token: YOUR_ADMIN_TOKEN'
```

### Shell & platform examples

Replace `HOST-LAN-IP` with your host IP (e.g. `192.168.1.50`) and `PASTE_ID` with the returned 12-character ID.

#### Bash / zsh (curl)

- **Create a paste from a string:**
  ```sh
  printf 'hello from bash\n' | curl -fsS http://HOST-LAN-IP:8000/api/pastes \
    -H 'X-Paste-Title: bash snippet' \
    --data-binary @-
  ```
- **Send a local file with 7-day expiry:**
  ```sh
  curl -fsS http://HOST-LAN-IP:8000/api/pastes \
    -H 'X-Paste-Title: app config' \
    -H 'X-Paste-TTL: 168' \
    --data-binary @./config.yaml
  ```
- **Read paste by ID:**
  ```sh
  curl -fsS http://HOST-LAN-IP:8000/api/pastes/PASTE_ID
  ```
- **Parse JSON response and open URL in browser:**
  ```sh
  URL=$(printf 'quick link' | curl -fsS http://HOST-LAN-IP:8000/api/pastes --data-binary @- | jq -r .url)
  xdg-open "$URL"  # on macOS: open "$URL"
  ```

#### PowerShell (Windows / macOS / Linux)

- **Create a paste using `Invoke-RestMethod` (JSON):**
  ```powershell
  $body = @{
      title = "powershell note"
      content = "hello from powershell"
      ttl_hours = 24
  } | ConvertTo-Json

  $response = Invoke-RestMethod -Uri "http://HOST-LAN-IP:8000/api/pastes" -Method Post `
      -ContentType "application/json; charset=utf-8" `
      -Body $body

  Write-Host "Paste URL: $($response.url)"
  Start-Process $response.url
  ```
- **Send a local file as raw text:**
  ```powershell
  $content = Get-Content -Raw -Encoding utf8 .\config.yaml
  $response = Invoke-RestMethod -Uri "http://HOST-LAN-IP:8000/api/pastes" -Method Post `
      -Headers @{ "X-Paste-Title" = "config snippet"; "X-Paste-TTL" = "168" } `
      -ContentType "text/plain; charset=utf-8" `
      -Body $content

  $response.url
  ```
- **Read paste by ID:**
  ```powershell
  $paste = Invoke-RestMethod -Uri "http://HOST-LAN-IP:8000/api/pastes/PASTE_ID"
  $paste.content
  ```
- *Platform note:* In Windows PowerShell 5.1, explicitly specify `-Encoding utf8` on `Get-Content` to avoid ANSI/OEM character conversion on non-ASCII text. PowerShell 7+ defaults to UTF-8 without BOM.

#### Windows Command Prompt (cmd.exe)

Modern Windows 10 and 11 include `curl.exe` out of the box:

- **Create a paste from a local file:**
  ```cmd
  curl.exe -fsS http://HOST-LAN-IP:8000/api/pastes ^
    -H "X-Paste-Title: cmd snippet" ^
    -H "X-Paste-TTL: 24" ^
    --data-binary @config.yaml
  ```
- **Send text from stdin:**
  ```cmd
  echo hello from cmd| curl.exe -fsS http://HOST-LAN-IP:8000/api/pastes --data-binary @-
  ```
- **Read paste by ID:**
  ```cmd
  curl.exe -fsS http://HOST-LAN-IP:8000/api/pastes/PASTE_ID
  ```
- **Open paste URL in default browser:**
  ```cmd
  start http://HOST-LAN-IP:8000/p/PASTE_ID
  ```
- *Platform note:* `cmd.exe` uses `^` for line continuation and double quotes (`"`) for header arguments. Notice there is no space between the text and pipe (`|`) in `echo text|` to prevent trailing whitespace from being appended to the paste content.

## Maintenance

```sh
docker compose logs --tail=100
docker compose restart
docker compose down             # keeps named volume and pastes
docker compose down -v          # DELETES the database volume and all pastes
```

Back up the SQLite database by stopping the service briefly, copying the named volume's `pastes.db` and any `pastes.db-wal` / `pastes.db-shm` files if present, then starting it again. For a straightforward consistent backup, stop the container first.

## Security notes

- Designed for trusted private networks, not the public internet.
- Do not port-forward TCP/8000 on your router.
- `0.0.0.0:8000` in Compose publishes on host interfaces; enforce firewall rules for LAN and Tailscale access.
- The admin token is required from `.env`; anyone with it can delete pastes.
- Paste contents are not encrypted in SQLite. Anyone with host or Docker-volume access can read them.
- The app limits paste size to 1 MiB and escapes content in HTML templates.
- This MVP does not provide per-user authentication. Anyone who can reach it can create and read pastes. Restrict network access accordingly.
