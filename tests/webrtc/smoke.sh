#!/usr/bin/env bash
set -euo pipefail

image="${1:?Pass the image to test}"
result_dir="${RUNNER_TEMP:-/tmp}/steel-webrtc-smoke"
container="steel-webrtc-smoke-${RANDOM}"
mkdir -p "$result_dir"
cleanup() {
  docker logs "$container" > "$result_dir/container.log" 2>&1 || true
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d --name "$container" --memory=2g --cpus=3 --shm-size=512m \
  --tmpfs /recordings:size=128m \
  -p 127.0.0.1:3000:3000 -p 127.0.0.1:3001:3001 \
  -p 127.0.0.1:10000-10010:10000-10010/udp \
  -e CHROME_HEADLESS=false -e EXTERNAL_IP=127.0.0.1 \
  -e 'ICE_SERVERS_JSON=[]' -e NODE_ENV=production "$image"

ready=false
for ((attempt=0; attempt<40; attempt++)); do
  if curl --max-time 2 -fsS http://127.0.0.1:3000/v1/health >/dev/null 2>&1 && \
     curl --max-time 2 -fsS http://127.0.0.1:3001/sessions/debug >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  echo 'The API and RTC player did not become ready.' >&2
  exit 1
fi

timeout 45s python3 tests/webrtc/receive.py > "$result_dir/media.json"
python3 - "$result_dir/media.json" <<'PY'
import json
import sys
with open(sys.argv[1]) as stream:
    result = json.load(stream)
print(json.dumps(result, indent=2))
assert result['mediaPassed'], 'No actual decoded video frames'
assert result['frames'] >= 30, 'Too few decoded frames'
assert (result['width'], result['height']) == (1920, 1080)
assert result['connectionState'] == 'connected'
PY
