#!/usr/bin/env bash
# detect_env.sh - decide which maidr binding to use for this machine and project.
#
# Prints ONE JSON object describing runtimes (Python, R, Node), whether py-maidr /
# r-maidr are already installed, project-type signals in a directory, which maidr.js
# CDN hosts are reachable from here, and a recommendation:
#   "binding"   : "r-maidr" | "py-maidr" | "maidr-js"
#   "js_source" : "jsdelivr" | "cdnjs" | "bundle"   (how a page should load maidr.js)
#
# Usage:  bash detect_env.sh [PROJECT_DIR]        (default: current directory)
# Needs only POSIX utilities; curl or wget is optional (network probes degrade to "unknown").
# The network probe reflects THIS machine. A reader's browser may sit behind a different
# firewall, so pages should still carry a CDN -> CDN -> local fallback chain when possible.

MAIDR_JS_VERSION="4.6.0"
DIR="${1:-.}"
have() { command -v "$1" >/dev/null 2>&1; }
json_str() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\r\n'; }

# ---------- Python ----------
PY_CMD=""; PY_VER=""; PY_MAIDR=""; PIP=false; UV=false
FIRST_CMD=""; FIRST_VER=""
for c in python3 python py; do   # prefer an interpreter that already has py-maidr
  have "$c" || continue
  v=$("$c" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null | tr -d '\r')
  [ -n "$v" ] || continue
  if [ -z "$FIRST_CMD" ]; then FIRST_CMD="$c"; FIRST_VER="$v"; fi
  m=$("$c" -c 'import maidr;print(getattr(maidr,"__version__","installed"))' 2>/dev/null | tr -d '\r')
  if [ -n "$m" ]; then PY_CMD="$c"; PY_VER="$v"; PY_MAIDR="$m"; break; fi
done
if [ -z "$PY_CMD" ]; then PY_CMD="$FIRST_CMD"; PY_VER="$FIRST_VER"; fi
if [ -n "$PY_CMD" ]; then
  "$PY_CMD" -m pip --version >/dev/null 2>&1 && PIP=true
fi
have uv && UV=true

# ---------- R ----------
RSCRIPT=""; R_VER=""; R_MAIDR=""
if have Rscript; then RSCRIPT="Rscript"; fi
if [ -z "$RSCRIPT" ]; then  # Windows installs are often not on PATH
  for d in "/c/Program Files/R" "${LOCALAPPDATA:-/nonexistent}/Programs/R"; do
    [ -d "$d" ] || continue
    cand=$(ls -d "$d"/R-* 2>/dev/null | sort -V | tail -n1)
    if [ -n "$cand" ] && [ -x "$cand/bin/x64/Rscript.exe" ]; then RSCRIPT="$cand/bin/x64/Rscript.exe"; break; fi
    if [ -n "$cand" ] && [ -x "$cand/bin/Rscript.exe" ]; then RSCRIPT="$cand/bin/Rscript.exe"; break; fi
  done
fi
if [ -n "$RSCRIPT" ]; then
  R_VER=$("$RSCRIPT" -e 'cat(as.character(getRversion()))' 2>/dev/null | tr -d '\r\n')
  R_MAIDR=$("$RSCRIPT" -e 'cat(tryCatch(as.character(packageVersion("maidr")), error=function(e) ""))' 2>/dev/null | tr -d '\r\n')
fi

# ---------- Node ----------
NODE_VER=""; have node && NODE_VER=$(node --version 2>/dev/null | tr -d 'v\r\n')

# ---------- Project signals (depth <= 3, skipping heavy dirs) ----------
count() {
  find "$DIR" -maxdepth 3 \( -name node_modules -o -name .git -o -name .venv -o -name venv -o -name renv \) -prune \
    -o -type f "$@" -print 2>/dev/null | wc -l | tr -d ' '
}
R_FILES=$(count \( -iname '*.R' -o -name '*.Rmd' -o -name 'DESCRIPTION' -o -name 'renv.lock' -o -name '*.Rproj' \))
PY_FILES=$(count \( -name '*.py' -o -name '*.ipynb' -o -name 'pyproject.toml' -o -name 'requirements*.txt' -o -name 'Pipfile' -o -name 'environment.yml' -o -name 'uv.lock' \))
JS_FILES=$(count \( -name 'package.json' -o -name '*.js' -o -name '*.mjs' -o -name '*.ts' -o -name '*.tsx' -o -name '*.jsx' -o -name '*.svelte' -o -name '*.vue' \))
# Quarto documents count toward whichever engine their chunks use.
QMD_R=0; QMD_PY=0
while IFS= read -r q; do
  [ -n "$q" ] || continue
  grep -q '```{r' "$q" 2>/dev/null && QMD_R=$((QMD_R+1))
  grep -q '```{python' "$q" 2>/dev/null && QMD_PY=$((QMD_PY+1))
done <<QMDS
$(find "$DIR" -maxdepth 3 -name '*.qmd' -not -path '*/node_modules/*' 2>/dev/null)
QMDS
R_SIGNALS=$((R_FILES+QMD_R)); PY_SIGNALS=$((PY_FILES+QMD_PY)); JS_SIGNALS=$JS_FILES

# ---------- Network probes ----------
probe() {  # prints true|false|unknown
  if have curl; then
    code=$(curl -sS -m 6 -o /dev/null -w '%{http_code}' -I "$1" 2>/dev/null)
    case "$code" in 2*|3*) echo true;; *) echo false;; esac
  elif have wget; then
    wget -q --spider -T 6 "$1" >/dev/null 2>&1 && echo true || echo false
  else echo unknown; fi
}
JSDELIVR=$(probe "https://cdn.jsdelivr.net/npm/maidr@${MAIDR_JS_VERSION}/dist/maidr.js")
CDNJS=$(probe "https://cdnjs.cloudflare.com/ajax/libs/maidr/${MAIDR_JS_VERSION}/maidr.min.js")
PYPI=$(probe "https://pypi.org/simple/maidr/")
CRAN=$(probe "https://cloud.r-project.org/web/packages/maidr/index.html")

# ---------- Recommendation ----------
REASON=""
if [ "$R_SIGNALS" -gt 0 ] && [ "$R_SIGNALS" -ge "$PY_SIGNALS" ]; then
  BINDING="r-maidr"; REASON="R project files found; use the maidr R package (CRAN)."
  [ -z "$RSCRIPT" ] && REASON="$REASON R runtime not found here, so write the R code but tell the user you could not execute it."
elif [ "$PY_SIGNALS" -eq 0 ] && [ "$R_SIGNALS" -eq 0 ] && [ "$JS_SIGNALS" -gt 0 ] && [ -n "$NODE_VER" ]; then
  BINDING="maidr-js"; REASON="JavaScript project with no Python or R files; attach maidr.js (adapter or hand-authored JSON) to the web chart."
elif [ -n "$PY_CMD" ] && { [ -n "$PY_MAIDR" ] || [ "$PYPI" != "false" ]; }; then
  BINDING="py-maidr"; REASON="Python available; use py-maidr (pip install maidr)."
  [ -z "$PY_MAIDR" ] && REASON="$REASON py-maidr is not installed yet."
elif [ -n "$PY_CMD" ]; then
  BINDING="maidr-js"; REASON="Python is present but PyPI is unreachable and py-maidr is not installed; fall back to maidr.js."
else
  BINDING="maidr-js"; REASON="No Python runtime found; fall back to maidr.js in the browser."
fi
if [ "$JSDELIVR" = "true" ]; then JS_SOURCE="jsdelivr"
elif [ "$CDNJS" = "true" ]; then JS_SOURCE="cdnjs"
elif [ "$JSDELIVR" = "unknown" ]; then JS_SOURCE="jsdelivr"
else JS_SOURCE="bundle"; fi

b() { if [ -n "$1" ]; then echo true; else echo false; fi; }
q() { if [ -n "$1" ]; then printf '"%s"' "$(json_str "$1")"; else printf 'null'; fi; }
cat <<JSON
{
  "maidr_js_version": "${MAIDR_JS_VERSION}",
  "project_dir": $(q "$DIR"),
  "python": { "available": $(b "$PY_CMD"), "command": $(q "$PY_CMD"), "version": $(q "$PY_VER"), "pip": $PIP, "uv": $UV, "py_maidr_version": $(q "$PY_MAIDR") },
  "r": { "available": $(b "$RSCRIPT"), "rscript": $(q "$RSCRIPT"), "version": $(q "$R_VER"), "r_maidr_version": $(q "$R_MAIDR") },
  "node": { "available": $(b "$NODE_VER"), "version": $(q "$NODE_VER") },
  "project_signals": { "r": $R_SIGNALS, "python": $PY_SIGNALS, "javascript": $JS_SIGNALS },
  "network": { "jsdelivr": $JSDELIVR, "cdnjs": $CDNJS, "pypi": $PYPI, "cran": $CRAN },
  "recommendation": { "binding": "$BINDING", "js_source": "$JS_SOURCE", "reason": $(q "$REASON") }
}
JSON
