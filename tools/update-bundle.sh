#!/usr/bin/env bash
# Refresh the vendored maidr.js bundle and rewrite the version pins across the skill.
#
# Usage: tools/update-bundle.sh [VERSION]      (default: the "latest" dist-tag on npm)
# Requires curl and python3. Downloads from jsDelivr (a mirror of the npm tarball), records
# SHA-256 digests in skills/maidr/assets/maidr-bundle.json, and replaces the previous version
# string everywhere it is pinned. Prints a warning if cdnjs has not mirrored the version yet.
# Also copies the release's dist/dotpad-sdk.json (the DotPad SDK pin maidr.js is built against)
# over skills/maidr/assets/dotpad-sdk.json when the release ships one; otherwise the asset is
# left alone and the script says so.
# Waits for the registry to serve VERSION before fetching anything, for up to an hour; see below.
# MAIDR_NPM_REGISTRY, MAIDR_FETCH_MAX_ATTEMPTS and MAIDR_FETCH_RETRY_DELAY override the registry
# and the wait so a test can stand in for both; nothing in CI sets them.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
ASSETS="$ROOT/skills/maidr/assets"
META="$ASSETS/maidr-bundle.json"
DOTPAD="$ASSETS/dotpad-sdk.json"
PY=$(command -v python3 || command -v python)
REGISTRY="${MAIDR_NPM_REGISTRY:-https://registry.npmjs.org/maidr}"
MAX_ATTEMPTS="${MAIDR_FETCH_MAX_ATTEMPTS:-60}"
RETRY_DELAY="${MAIDR_FETCH_RETRY_DELAY:-60}"

OLD=$("$PY" -c "import json;print(json.load(open(r'$META'))['version'])")
VER="${1:-}"
if [ -z "$VER" ]; then
  VER=$(curl -fsSL "$REGISTRY/latest" | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["version"])')
fi
# The version reaches URLs, a sed pattern and file contents, and on a dispatch it comes from
# another repository's payload, so only a plain release version gets past this point.
if ! printf '%s' "$VER" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "not a maidr release version: '$VER'" >&2
  exit 1
fi
echo "vendored: $OLD  ->  target: $VER"

# `npm publish` returns before the registry serves what it accepted: maidr 4.9.0 appeared about
# ten minutes after maidr's publish step ended, and 4.11.0 eighteen (15:19:22 to 15:37:44 UTC).
# A dispatch or a manual run can arrive inside that window (maidr's release workflow sent 4.11.0's
# the moment its publish step ended), and jsDelivr mirrors the registry, so fetching straight away
# 404s and leaves the release to the daily run. So check every RETRY_DELAY seconds, MAX_ATTEMPTS
# times: an hour by default, over three times the longest lag seen. A version the registry already
# serves, `latest` included, passes the first check.
# Every failure is retried, not only a 404, and nothing below runs until the version is served,
# so giving up leaves the working tree as it was.
attempt=1
until curl -fsS -o /dev/null "$REGISTRY/$VER"; do
  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "maidr $VER is still not on the registry after $attempt checks; giving up" >&2
    exit 1
  fi
  echo "maidr $VER is not on the registry yet (check $attempt of $MAX_ATTEMPTS); checking again in ${RETRY_DELAY}s" >&2
  attempt=$((attempt + 1))
  sleep "$RETRY_DELAY"
done

TMP=$(mktemp -d)
for f in maidr.js maidr-math.css; do
  curl -fsSL "https://cdn.jsdelivr.net/npm/maidr@$VER/dist/$f" -o "$TMP/$f"
done
cp "$TMP/maidr.js" "$ASSETS/maidr.js"
cp "$TMP/maidr-math.css" "$ASSETS/maidr-math.css"

if ! curl -fsSI "https://cdnjs.cloudflare.com/ajax/libs/maidr/$VER/maidr.min.js" >/dev/null 2>&1; then
  echo "WARNING: cdnjs does not serve maidr $VER yet; the cdnjs fallback URL will 404 until it catches up." >&2
fi

# The DotPad SDK pin: maidr.js ships the manifest it imports the SDK from as dist/dotpad-sdk.json,
# so the skill copies that rather than maintaining its own. `curl -f` fails on a 404 (a release
# that predates the manifest), and the JSON check guards against an error page served as 200.
if curl -fsSL "https://cdn.jsdelivr.net/npm/maidr@$VER/dist/dotpad-sdk.json" -o "$TMP/dotpad-sdk.json" 2>/dev/null \
   && DOTPAD_VER=$("$PY" -c 'import json,sys;m=json.load(open(sys.argv[1]));v=m.get("version");print(v) if isinstance(v,str) and v else sys.exit(1)' "$TMP/dotpad-sdk.json" 2>/dev/null); then
  cp "$TMP/dotpad-sdk.json" "$DOTPAD"
  echo "dotpad sdk pin: $DOTPAD_VER (from maidr@$VER dist/dotpad-sdk.json)"
else
  echo "maidr $VER does not ship dist/dotpad-sdk.json; leaving skills/maidr/assets/dotpad-sdk.json as it is ($("$PY" -c "import json;print(json.load(open(r'$DOTPAD'))['version'])"))"
fi

"$PY" - "$META" "$ASSETS" "$VER" <<'EOF'
import hashlib, json, os, sys, datetime
meta_path, assets, ver = sys.argv[1:4]
meta = json.load(open(meta_path))
before = json.dumps(meta, sort_keys=True)
meta["version"] = ver
meta["source"] = f"https://cdn.jsdelivr.net/npm/maidr@{ver}/dist/"
meta["registry"] = f"https://registry.npmjs.org/maidr/{ver}"
for name in ("maidr.js", "maidr-math.css"):
    data = open(os.path.join(assets, name), "rb").read()
    meta["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
meta["cdn"] = {
    "jsdelivr": f"https://cdn.jsdelivr.net/npm/maidr@{ver}/dist/maidr.js",
    "cdnjs": f"https://cdnjs.cloudflare.com/ajax/libs/maidr/{ver}/maidr.min.js",
}
# "retrieved" dates the vendored bytes, not the last run of this script. Bumping it
# unconditionally leaves a diff behind on a re-vendor of the same release, which would make
# the update-bundle workflow commit an empty refresh on every run.
if json.dumps(meta, sort_keys=True) != before:
    meta["retrieved"] = datetime.date.today().isoformat()
with open(meta_path, "w") as fh:
    json.dump(meta, fh, indent=2)
    fh.write("\n")
EOF

if [ "$OLD" != "$VER" ]; then
  OLD_RE=$(printf '%s' "$OLD" | sed 's/\./\\./g')
  grep -rl --exclude-dir=__pycache__ --exclude=maidr.js --exclude=maidr-math.css --exclude=maidr-bundle.json "$OLD" \
    "$ROOT/skills/maidr" "$ROOT/README.md" "$ROOT/AGENTS.md" 2>/dev/null \
    | while IFS= read -r file; do
        sed -i "s/\b${OLD_RE}\b/${VER}/g" "$file"
        echo "pinned $VER in ${file#$ROOT/}"
      done
fi
rm -rf "$TMP"
echo "done: maidr $VER vendored"
