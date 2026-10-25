#!/usr/bin/env bash
set -euo pipefail
export COMPOSE_PROJECT_NAME=codex25lan4disposable
unset PASTE_ADMIN_TOKEN
if docker compose --env-file /dev/null config --quiet > missing-token.log 2>&1; then
  echo 'Missing token unexpectedly accepted'; exit 1
fi
grep -q 'Set PASTE_ADMIN_TOKEN' missing-token.log
export PASTE_ADMIN_TOKEN=disposable-ci-test-token
trap 'docker compose down -v --remove-orphans' EXIT
docker compose config --quiet > config.log
test ! -s config.log
docker compose build
docker compose up -d
for attempt in $(seq 1 40); do
  if curl -fsS -I http://127.0.0.1:8000/ > root-headers.log; then break; fi
  sleep 1
done
grep -q '200 OK' root-headers.log
docker compose ps -a
docker ps --filter publish=8000 --format 'table {{.Names}}\t{{.Ports}}' | tee listener.log
grep -q lan-paste listener.log
image=$(docker compose images -q lan-paste)
if docker run --rm -p 8000:8000 "$image" python -m http.server 8000 > port-conflict.log 2>&1; then
  echo 'Occupied port unexpectedly accepted'; exit 1
fi
grep -Ei 'allocated|already in use' port-conflict.log
docker compose exec -T lan-paste sh -c 'id; ls -ld /data'
test "$(docker compose exec -T --user appuser lan-paste id -u)" = 10001
if docker compose run --rm -e DEFAULT_TTL_HOURS=invalid lan-paste python -c 'import app' > invalid-ttl.log 2>&1; then
  echo 'Invalid TTL unexpectedly accepted'; exit 1
fi
grep -q ValueError invalid-ttl.log
curl -fsS http://127.0.0.1:8000/api/pastes -H 'Content-Type: application/json' --data '{"content":"disposable fixture","ttl_hours":"never"}' > created.json
paste_id=$(python -c 'import json; print(json.load(open("created.json"))["id"])')
test "$(curl -s -o /dev/null -w '%{http_code}' -X DELETE http://127.0.0.1:8000/api/pastes/$paste_id -H 'X-Admin-Token: wrong')" = 403
docker compose down
docker volume ls --filter label=com.docker.compose.volume=paste_data | tee volumes.log
grep -q codex25lan4disposable_paste_data volumes.log
docker compose up -d
for attempt in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/api/pastes/$paste_id > preserved.json; then break; fi
  sleep 1
done
python -c 'import json; assert json.load(open("preserved.json"))["content"] == "disposable fixture"'
docker compose exec -T lan-paste python -c "import sqlite3; db=sqlite3.connect('/data/pastes.db'); db.execute(\"UPDATE pastes SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?\", ('$paste_id',)); db.commit()"
test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/pastes/$paste_id)" = 404
docker compose exec -T lan-paste python -c "import sqlite3; assert sqlite3.connect('/data/pastes.db').execute('SELECT COUNT(*) FROM pastes').fetchone()[0] == 0"
curl -fsS http://127.0.0.1:8000/api/pastes --data-binary 'disposable second fixture' > recreated.json
second_id=$(python -c 'import json; print(json.load(open("recreated.json"))["id"])')
docker compose logs --tail=100 lan-paste > service.log
! grep -q "$PASTE_ADMIN_TOKEN" service.log
# Only this runner's explicitly named disposable fixture project is removed.
test "$COMPOSE_PROJECT_NAME" = codex25lan4disposable
docker compose down -v
docker compose up -d
for attempt in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/api/pastes > empty.json; then break; fi
  sleep 1
done
python -c 'import json; assert json.load(open("empty.json"))["pastes"] == []'
test "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/pastes/$second_id)" = 404
echo 'All disposable Compose troubleshooting checks passed'
