#!/usr/bin/env bash
# Refresh the vendored maidr.js bundle and rewrite the version pins across the skill.
#
# Usage: tools/update-bundle.sh [VERSION]      (default: the "latest" dist-tag on npm)
# Requires curl and python3. Downloads from jsDelivr (a mirror of the npm tarball), records
# SHA-256 digests in skills/maidr/assets/maidr-bundle.json, and replaces the previous version
# string everywhere it is pinned. Prints a warning if cdnjs has not mirrored the version yet.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
ASSETS="$ROOT/skills/maidr/assets"
META="$ASSETS/maidr-bundle.json"
PY=$(command -v python3 || command -v python)

OLD=$("$PY" -c "import json;print(json.load(open(r'$META'))['version'])")
VER="${1:-}"
if [ -z "$VER" ]; then
  VER=$(curl -fsSL https://registry.npmjs.org/maidr/latest | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["version"])')
fi
echo "vendored: $OLD  ->  target: $VER"

TMP=$(mktemp -d)
for f in maidr.js maidr-math.css; do
  curl -fsSL "https://cdn.jsdelivr.net/npm/maidr@$VER/dist/$f" -o "$TMP/$f"
done
cp "$TMP/maidr.js" "$ASSETS/maidr.js"
cp "$TMP/maidr-math.css" "$ASSETS/maidr-math.css"

if ! curl -fsSI "https://cdnjs.cloudflare.com/ajax/libs/maidr/$VER/maidr.min.js" >/dev/null 2>&1; then
  echo "WARNING: cdnjs does not serve maidr $VER yet; the cdnjs fallback URL will 404 until it catches up." >&2
fi

"$PY" - "$META" "$ASSETS" "$VER" <<'EOF'
import hashlib, json, os, sys, datetime
meta_path, assets, ver = sys.argv[1:4]
meta = json.load(open(meta_path))
meta["version"] = ver
meta["source"] = f"https://cdn.jsdelivr.net/npm/maidr@{ver}/dist/"
meta["registry"] = f"https://registry.npmjs.org/maidr/{ver}"
meta["retrieved"] = datetime.date.today().isoformat()
for name in ("maidr.js", "maidr-math.css"):
    data = open(os.path.join(assets, name), "rb").read()
    meta["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
meta["cdn"] = {
    "jsdelivr": f"https://cdn.jsdelivr.net/npm/maidr@{ver}/dist/maidr.js",
    "cdnjs": f"https://cdnjs.cloudflare.com/ajax/libs/maidr/{ver}/maidr.min.js",
}
json.dump(meta, open(meta_path, "w"), indent=2)
open(meta_path, "a").write("\n")
EOF

if [ "$OLD" != "$VER" ]; then
  OLD_RE=$(printf '%s' "$OLD" | sed 's/\./\\./g')
  grep -rl --exclude=maidr.js --exclude=maidr-math.css --exclude=maidr-bundle.json "$OLD" \
    "$ROOT/skills/maidr" "$ROOT/README.md" "$ROOT/AGENTS.md" 2>/dev/null \
    | while IFS= read -r file; do
        sed -i "s/\b${OLD_RE}\b/${VER}/g" "$file"
        echo "pinned $VER in ${file#$ROOT/}"
      done
fi
rm -rf "$TMP"
echo "done: maidr $VER vendored"
