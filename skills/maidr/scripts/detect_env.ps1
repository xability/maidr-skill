#requires -Version 5.1
<#
.SYNOPSIS
  detect_env.ps1 - PowerShell twin of detect_env.sh. Prints ONE JSON object with the
  same shape: runtimes, installed maidr bindings, project signals, CDN reachability, and
  a recommendation ("binding": r-maidr | py-maidr | maidr-js; "js_source": jsdelivr | cdnjs | bundle).
.EXAMPLE
  pwsh -File detect_env.ps1            # current directory
  pwsh -File detect_env.ps1 C:\proj    # another project directory
#>
param([string]$Dir = ".")
$ErrorActionPreference = "SilentlyContinue"
$MaidrJsVersion = "4.6.0"

function Try-Run([string]$exe, [string[]]$arguments) {
  try {
    $out = & $exe @arguments 2>$null
    if ($null -ne $out) { return ($out | Out-String).Trim() }
  } catch {}
  return $null
}

# ---------- Python ----------
$pyCmd = $null; $pyVer = $null; $pyMaidr = $null; $pip = $false
$firstCmd = $null; $firstVer = $null
foreach ($c in @("python3", "python", "py")) {   # prefer an interpreter that already has py-maidr
  if (-not (Get-Command $c -ErrorAction SilentlyContinue)) { continue }
  $v = Try-Run $c @("-c", 'import sys;print("%d.%d.%d"%sys.version_info[:3])')
  if ($v -notmatch '^\d+\.\d+\.\d+$') { continue }
  if (-not $firstCmd) { $firstCmd = $c; $firstVer = $v }
  $m = Try-Run $c @("-c", 'import maidr;print(getattr(maidr,"__version__","installed"))')
  if ($m -and $m -match '^(\d|installed)') { $pyCmd = $c; $pyVer = $v; $pyMaidr = $m; break }
}
if (-not $pyCmd) { $pyCmd = $firstCmd; $pyVer = $firstVer }
if ($pyCmd) {
  if (Try-Run $pyCmd @("-m", "pip", "--version")) { $pip = $true }
}
$uv = [bool](Get-Command uv -ErrorAction SilentlyContinue)

# ---------- R ----------
$rscript = $null
if (Get-Command Rscript -ErrorAction SilentlyContinue) { $rscript = "Rscript" }
if (-not $rscript) {
  foreach ($root in @("$env:ProgramFiles\R", "$env:LOCALAPPDATA\Programs\R")) {
    if (Test-Path $root) {
      $cand = Get-ChildItem $root -Directory -Filter "R-*" | Sort-Object Name -Descending | Select-Object -First 1
      if ($cand) {
        foreach ($p in @("$($cand.FullName)\bin\x64\Rscript.exe", "$($cand.FullName)\bin\Rscript.exe")) {
          if (Test-Path $p) { $rscript = $p; break }
        }
      }
    }
    if ($rscript) { break }
  }
}
$rVer = $null; $rMaidr = $null
if ($rscript) {
  $rVer = Try-Run $rscript @("-e", "cat(as.character(getRversion()))")
  $rMaidr = Try-Run $rscript @("-e", 'cat(tryCatch(as.character(packageVersion("maidr")), error=function(e) ""))')
  if ($rMaidr -eq "") { $rMaidr = $null }
}

# ---------- Node ----------
$nodeVer = $null
if (Get-Command node -ErrorAction SilentlyContinue) { $nodeVer = (Try-Run node @("--version")) -replace '^v', '' }

# ---------- Project signals ----------
$skip = '\\(node_modules|\.git|\.venv|venv|renv)(\\|$)'
$files = Get-ChildItem -Path $Dir -Recurse -File -Depth 3 -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch $skip }
$rSignals  = @($files | Where-Object { $_.Extension -in ".R", ".r", ".Rmd", ".Rproj" -or $_.Name -in "DESCRIPTION", "renv.lock" }).Count
$pySignals = @($files | Where-Object { $_.Extension -in ".py", ".ipynb" -or $_.Name -in "pyproject.toml", "Pipfile", "environment.yml", "uv.lock" -or $_.Name -like "requirements*.txt" }).Count
$jsSignals = @($files | Where-Object { $_.Extension -in ".js", ".mjs", ".ts", ".tsx", ".jsx", ".svelte", ".vue" -or $_.Name -eq "package.json" }).Count
foreach ($q in ($files | Where-Object { $_.Extension -eq ".qmd" })) {
  $txt = Get-Content $q.FullName -Raw
  if ($txt -match '```\{r') { $rSignals++ }
  if ($txt -match '```\{python') { $pySignals++ }
}

# ---------- Network probes ----------
function Probe([string]$url) {
  try {
    $r = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 6 -UseBasicParsing
    return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400)
  } catch { return $false }
}
$jsdelivr = Probe "https://cdn.jsdelivr.net/npm/maidr@$MaidrJsVersion/dist/maidr.js"
$cdnjs    = Probe "https://cdnjs.cloudflare.com/ajax/libs/maidr/$MaidrJsVersion/maidr.min.js"
$pypi     = Probe "https://pypi.org/simple/maidr/"
$cran     = Probe "https://cloud.r-project.org/web/packages/maidr/index.html"

# ---------- Recommendation ----------
if ($rSignals -gt 0 -and $rSignals -ge $pySignals) {
  $binding = "r-maidr"; $reason = "R project files found; use the maidr R package (CRAN)."
  if (-not $rscript) { $reason += " R runtime not found here, so write the R code but tell the user you could not execute it." }
} elseif ($pySignals -eq 0 -and $rSignals -eq 0 -and $jsSignals -gt 0 -and $nodeVer) {
  $binding = "maidr-js"; $reason = "JavaScript project with no Python or R files; attach maidr.js (adapter or hand-authored JSON) to the web chart."
} elseif ($pyCmd -and ($pyMaidr -or $pypi)) {
  $binding = "py-maidr"; $reason = "Python available; use py-maidr (pip install maidr)."
  if (-not $pyMaidr) { $reason += " py-maidr is not installed yet." }
} elseif ($pyCmd) {
  $binding = "maidr-js"; $reason = "Python is present but PyPI is unreachable and py-maidr is not installed; fall back to maidr.js."
} else {
  $binding = "maidr-js"; $reason = "No Python runtime found; fall back to maidr.js in the browser."
}
$jsSource = if ($jsdelivr) { "jsdelivr" } elseif ($cdnjs) { "cdnjs" } else { "bundle" }

[ordered]@{
  maidr_js_version = $MaidrJsVersion
  project_dir      = $Dir
  python  = [ordered]@{ available = [bool]$pyCmd; command = $pyCmd; version = $pyVer; pip = $pip; uv = $uv; py_maidr_version = $pyMaidr }
  r       = [ordered]@{ available = [bool]$rscript; rscript = $rscript; version = $rVer; r_maidr_version = $rMaidr }
  node    = [ordered]@{ available = [bool]$nodeVer; version = $nodeVer }
  project_signals = [ordered]@{ r = $rSignals; python = $pySignals; javascript = $jsSignals }
  network = [ordered]@{ jsdelivr = $jsdelivr; cdnjs = $cdnjs; pypi = $pypi; cran = $cran }
  recommendation  = [ordered]@{ binding = $binding; js_source = $jsSource; reason = $reason }
} | ConvertTo-Json -Depth 4
