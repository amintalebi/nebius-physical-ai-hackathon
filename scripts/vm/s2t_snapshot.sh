# Versioned, write-once model registry: ~/work/models/<version>/ (+ sha256, notes) and s3://.../models/<version>/.
# Usage: bash s2t_snapshot.sh <version> <pretrained_model dir> "<notes>"   (refuses to overwrite an existing version)
set -euo pipefail
V=$1; SRC=$2; NOTES=${3:-}; W=~/work; DST=$W/models/$V
[ -f "$SRC/model.safetensors" ] || { echo "no checkpoint at $SRC"; exit 1; }
if [ -e "$DST" ]; then echo "version $V exists, not overwriting"; exit 0; fi
mkdir -p $W/models && cp -r "$SRC" "$DST" && chmod -R a-w "$DST"
SHA=$(sha256sum "$DST/model.safetensors" | cut -c1-64)
python3 -c "import json,sys,datetime;print(json.dumps({'version':sys.argv[1],'source':sys.argv[2],'sha256':sys.argv[3],'notes':sys.argv[4],'saved_utc':datetime.datetime.utcnow().isoformat(timespec='seconds')}))" "$V" "$SRC" "$SHA" "$NOTES" >> $W/models/registry.jsonl
cd $W/s2t && AWS_PROFILE=nebius $W/venv_tools/bin/python scripts/nebius_s3.py put "$DST" s3://s2t-group02-a66c17/submission_draft/models/$V/ | tail -1
AWS_PROFILE=nebius $W/venv_tools/bin/python scripts/nebius_s3.py put $W/models/registry.jsonl s3://s2t-group02-a66c17/submission_draft/models/registry.jsonl | tail -1
echo "saved $V sha256 ${SHA:0:12}"
