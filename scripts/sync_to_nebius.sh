#!/bin/bash
# Push the submission folder to Nebius Object Storage, then list it back. "Your folder lands there by
# the cutoff or it doesn't exist" (brief), so the list-back is the proof, not the upload exit code.
#   BUCKET=s3://<bucket>/<team> REGION=eu-north1 ./scripts/sync_to_nebius.sh
# Credentials: Object Storage access key from the Nebius console in ~/.aws/credentials (profile nebius).
set -euo pipefail
cd "$(dirname "$0")/.."
BUCKET="${BUCKET:?s3://bucket/team-folder}"
REGION="${REGION:-eu-north1}"
EP="https://storage.${REGION}.nebius.cloud"
AWS=(aws --profile "${AWS_PROFILE:-nebius}" --endpoint-url "$EP")

python3 scripts/validate_manifest.py --out submission/manifest.json
"${AWS[@]}" s3 sync submission/ "$BUCKET/" --exclude "*.tmp"
echo "--- remote listing ---"
"${AWS[@]}" s3 ls --recursive --human-readable --summarize "$BUCKET/" | tee logs/last_sync_listing.txt
# Byte-level check on the manifest: what is remote must equal what we validated locally.
"${AWS[@]}" s3 cp "$BUCKET/manifest.json" - | cmp - submission/manifest.json && echo "manifest.json verified remote == local"
