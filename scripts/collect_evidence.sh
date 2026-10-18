#!/usr/bin/env bash
# Snapshot Nebius training evidence on the GPU VM and upload it to Object Storage (rubric "Nebius 20", see
# docs/roadmap/08-training-nebius.md "Nebius evidence" and 11-submission.md layout `nebius/`).
#
#   bash scripts/collect_evidence.sh                 # snapshot -> ~/work/evidence/<UTC timestamp>/ -> S3
#   NO_UPLOAD=1 bash scripts/collect_evidence.sh     # snapshot only
#   DEST=s3://<bucket>/<team>/nebius/evidence bash scripts/collect_evidence.sh
#
# Read-only on everything except the new snapshot folder. Safe to re-run: each run writes a new timestamped
# folder, and nebius_s3.py put skips objects already uploaded (same key and size). Missing logs, envs or repos
# are noted in the snapshot, never fatal. Never copies credentials; a pattern scan aborts the upload if a
# secret-looking string slips into the snapshot.
set -euo pipefail

WORK=${WORK:-$HOME/work}
DEST=${DEST:-s3://s2t-group02-a66c17/submission_draft/nebius/evidence}
S3PY=${S3PY:-$WORK/s2t/scripts/nebius_s3.py}
TOOLS_PY=${TOOLS_PY:-$WORK/venv_tools/bin/python}
UV=${UV:-$WORK/venv_tools/bin/uv}
INSTANCE_ID=${INSTANCE_ID:-computeinstance-e05kmxe3mvhpg3waqf}
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT=$WORK/evidence/$TS
mkdir -p "$OUT/logs" "$OUT/pip" "$OUT/git" "$OUT/reports"

# run <outfile> <cmd...>: capture stdout+stderr, record a failing exit code instead of aborting.
run() {
  local f=$1; shift
  { "$@" || echo "[collect_evidence] exit=$? : $*"; } > "$f" 2>&1 || true
}

# ---- machine ---------------------------------------------------------------------------------------------
{
  echo "snapshot_utc: $TS"
  echo "instance_id: $INSTANCE_ID"
  echo "hostname: $(hostname)"
  echo "kernel: $(uname -r)"
  echo "os: $(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-?}")"
  echo "nproc: $(nproc 2>/dev/null || echo ?)"
  echo "uptime: $(uptime 2>/dev/null || echo ?)"
} > "$OUT/machine.txt" 2>&1 || true
run "$OUT/free.txt" free -h
run "$OUT/df.txt" df -h
run "$OUT/nvidia-smi.txt" nvidia-smi
run "$OUT/nvidia-smi.csv" nvidia-smi \
  --query-gpu=timestamp,name,pci.bus_id,driver_version,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.max.sm \
  --format=csv
run "$OUT/nvidia-smi-apps.csv" nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
# What is running now (command lines only, truncated; our jobs take no secrets on the command line).
{ ps -eo pid,etime,cmd --sort=start_time | grep -E 'python|lerobot|collect|train|isaac|cosmos|vllm' \
    | grep -vE 'grep|networkd|unattended|telemetry' | cut -c1-300; } > "$OUT/processes.txt" 2>&1 || true

# ---- logs: summaries, not full copies (training step lines are copied in full) ---------------------------
shopt -s nullglob
for f in "$WORK"/logs/*.log "$WORK"/logs/*/*.log; do
  name=${f#"$WORK"/logs/}; name=${name//\//__}; name=${name%.log}
  # tqdm writes \r-separated progress; split it so INFO lines and markers land on their own lines.
  clean=$(mktemp)
  tr '\r' '\n' < "$f" | sed -E 's/(Training: *[0-9]+%[^I]*)(INFO )/\1\n\2/g' > "$clean" || true
  {
    echo "# $f"
    echo "size_bytes: $(stat -c %s "$f" 2>/dev/null || echo ?)"
    echo "first_write_utc: $(stat -c %w "$f" 2>/dev/null || echo ?)"
    echo "last_write_utc: $(stat -c %y "$f" 2>/dev/null || echo ?)"
    echo "lines: $(wc -l < "$clean")"
    echo
    echo "## markers (EXIT / *_DONE / done / Traceback / Error)"
    grep -nE '^EXIT=|_DONE|\[collect\] done|CHAIN_|Traceback|Error:|error:|failed on spot' "$clean" | cut -c1-300 | tail -40 || true
    echo
    echo "## collect"
    s=$(grep -cE '\[collect\] attempt [0-9]+: success' "$clean" || true)
    x=$(grep -cE '\[collect\] attempt [0-9]+: failed' "$clean" || true)
    echo "attempts_success: ${s:-0}  attempts_failed: ${x:-0}"
    grep -E '\[collect_grid\]|\[collect\] done' "$clean" | cut -c1-300 || true
    echo
    echo "## eval"
    grep -E '^\[eval\]' "$clean" | cut -c1-300 | tail -40 || true
    echo
    echo "## training (last 5 INFO step lines)"
    grep -oE 'INFO .*step:[0-9]+[KM]? smpl:.*' "$clean" | tail -5 || true
    echo
    echo "## head -5"
    grep -vE '^\s*$' "$clean" | head -5 | cut -c1-300 || true
    echo
    echo "## tail -25"
    grep -vE '^\s*$|^Training: ' "$clean" | tail -25 | cut -c1-300 || true
  } > "$OUT/logs/$name.summary.txt" 2>&1 || true
  grep -oE 'INFO .*step:[0-9]+[KM]? smpl:.*' "$clean" > "$OUT/logs/$name.steps.txt" 2>/dev/null || rm -f "$OUT/logs/$name.steps.txt"
  grep -E '\[collect\] attempt [0-9]+:' "$clean" > "$OUT/logs/$name.collect.txt" 2>/dev/null || rm -f "$OUT/logs/$name.collect.txt"
  rm -f "$clean"
done
[ -n "$(ls "$WORK"/logs 2>/dev/null)" ] || echo "no logs in $WORK/logs" > "$OUT/logs/MISSING.txt"
for r in "$WORK"/reports/*.jsonl "$WORK"/s2t/reports/*.jsonl "$WORK"/s2t/reports/*.md; do cp "$r" "$OUT/reports/" || true; done
ls -la "$WORK"/outputs/*/checkpoints/ > "$OUT/checkpoints_listing.txt" 2>&1 || true
for d in "$WORK"/outputs/*/checkpoints/*/pretrained_model; do
  [ -f "$d/model.safetensors" ] && sha256sum "$d/model.safetensors" >> "$OUT/checkpoints_sha256.txt" || true
done
shopt -u nullglob

# ---- environments -----------------------------------------------------------------------------------------
for env in "$WORK/env_isaaclab" "$WORK/env_lerobot" "$WORK/cosmos-transfer2.5/.venv"; do
  py=$env/bin/python
  tag=$(echo "${env#"$WORK"/}" | tr '/.' '__')
  if [ ! -x "$py" ]; then echo "missing: $py" > "$OUT/pip/$tag.txt"; continue; fi
  {
    echo "# $py ($("$py" --version 2>&1))"
    if "$py" -m pip --version >/dev/null 2>&1; then
      "$py" -m pip list --format=freeze 2>/dev/null
    elif [ -x "$UV" ]; then
      "$UV" pip list --format=freeze --python "$py" 2>/dev/null
    else
      echo "no pip or uv for $py"
    fi
  } > "$OUT/pip/$tag.txt" 2>&1 || true
done

# ---- source revisions -------------------------------------------------------------------------------------
for r in s2t so101_sim_pickplace IsaacLab lerobot cosmos-transfer2.5; do
  repo=$WORK/$r
  if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then echo "not a git repo: $repo" > "$OUT/git/$r.txt"; continue; fi
  {
    echo "# $repo"
    echo "remote: $(git -C "$repo" remote get-url origin 2>/dev/null | sed -E 's#//[^@/]*@#//***@#')"
    echo "head: $(git -C "$repo" rev-parse HEAD 2>/dev/null)"
    echo "describe: $(git -C "$repo" describe --always --tags --dirty 2>/dev/null)"
    echo "branch: $(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null)"
    echo
    echo "## log -5"
    git -C "$repo" log -5 --format='%h %ad %s' --date=iso-strict 2>/dev/null
    echo
    echo "## status --short"
    git -C "$repo" status --short 2>/dev/null | head -50
    echo
    echo "## diff --stat"
    git -C "$repo" diff --stat 2>/dev/null | tail -50
  } > "$OUT/git/$r.txt" 2>&1 || true
done

# ---- secret guard, index, upload --------------------------------------------------------------------------
if grep -rIlE 'aws_secret_access_key|AWS_SECRET|REASON_API_KEY=|Bearer [A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{30,}|(^|[^A-Za-z0-9])AKIA[A-Z0-9]{16}' "$OUT" >/dev/null 2>&1; then
  echo "[collect_evidence] secret-like string found in $OUT; not uploading. Files:" >&2
  grep -rIlE 'aws_secret_access_key|AWS_SECRET|REASON_API_KEY=|Bearer [A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{30,}|(^|[^A-Za-z0-9])AKIA[A-Z0-9]{16}' "$OUT" >&2 || true
  exit 2
fi
(cd "$OUT" && find . -type f ! -name INDEX.txt -printf '%10s  %p\n' | sort -k2) > "$OUT/INDEX.txt" || true
echo "[collect_evidence] snapshot at $OUT ($(find "$OUT" -type f | wc -l) files)"

if [ "${NO_UPLOAD:-0}" = 1 ]; then echo "[collect_evidence] NO_UPLOAD=1, skipping upload"; exit 0; fi
if [ ! -f "$S3PY" ]; then echo "[collect_evidence] $S3PY not found, skipping upload" >&2; exit 0; fi
export AWS_PROFILE=${AWS_PROFILE:-nebius}
"$TOOLS_PY" "$S3PY" put "$OUT" "$DEST/$TS"
"$TOOLS_PY" "$S3PY" ls "$DEST/$TS/" | tail -3
