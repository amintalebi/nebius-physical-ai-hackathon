#!/usr/bin/env python3
"""Nebius Object Storage from Python: probe, list, upload, download. No aws CLI needed on the VM.

Adapted from nebius/nebius-physical-ai @ 8195442 research/lerobot-deploy/s3_sync.py (Apache-2.0):
same endpoint scheme and boto3 calls, plus directory upload that skips files already uploaded
(same key and size), so it can be re-run after every checkpoint save on a preemptible VM.

    # Event defaults: region uk-south2, endpoint https://storage.uk-south2.nebius.cloud. Override with
    # NEBIUS_S3_ENDPOINT / AWS_ENDPOINT_URL and NEBIUS_REGION / AWS_DEFAULT_REGION (SecretStash field names).
    export AWS_PROFILE=nebius     # keys from SecretStash hackathon-object-storage, entered via `aws configure`

    python scripts/nebius_s3.py check s3://<bucket>/<team>/        # T+0:30: write, read back, delete 1 byte
    python scripts/nebius_s3.py put outputs/act_main s3://<bucket>/<team>/outputs/act_main
    python scripts/nebius_s3.py ls  s3://<bucket>/<team>/
    python scripts/nebius_s3.py get s3://<bucket>/<team>/outputs/act_main/checkpoints/040000 ckpt/

Keys: docs/roadmap/11-submission.md, "Credentials".
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


def endpoint() -> str:
    return (os.environ.get("NEBIUS_S3_ENDPOINT") or os.environ.get("AWS_ENDPOINT_URL")
            or f"https://storage.{region()}.nebius.cloud")


def region() -> str:
    return os.environ.get("NEBIUS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "uk-south2"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """s3://bucket/some/prefix -> ("bucket", "some/prefix"). The prefix may be empty."""
    if not uri.startswith("s3://"):
        raise ValueError(f"expected s3://bucket/prefix, got {uri!r}")
    bucket, _, prefix = uri[len("s3://"):].partition("/")
    if not bucket:
        raise ValueError(f"no bucket in {uri!r}")
    return bucket, prefix


def upload_plan(local: Path, prefix: str) -> list[tuple[Path, str]]:
    """Local file or directory -> [(file, key)]. A directory keeps its layout under `prefix`.
    A file goes to `prefix` itself, or to `prefix/<name>` when the prefix is empty or ends in '/'."""
    if local.is_file():
        if not prefix or prefix.endswith("/"):
            return [(local, prefix + local.name)]
        return [(local, prefix)]
    prefix = prefix.rstrip("/")
    files = sorted(p for p in local.rglob("*") if p.is_file())
    return [(p, f"{prefix}/{p.relative_to(local).as_posix()}" if prefix else p.relative_to(local).as_posix())
            for p in files]


def client():
    import boto3

    # No explicit keys: boto3 reads AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or AWS_PROFILE, the same
    # credentials scripts/sync_to_nebius.sh uses through the aws CLI.
    return boto3.client("s3", endpoint_url=endpoint(), region_name=region())


def iter_objects(c, bucket: str, prefix: str):
    for page in c.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        yield from page.get("Contents", [])


def cmd_check(args):
    bucket, prefix = parse_s3_uri(args.uri)
    c = client()
    key = f"{prefix.rstrip('/')}/.s2t_probe_{int(time.time())}".lstrip("/")
    print(f"endpoint {endpoint()}  bucket {bucket}")
    c.put_object(Bucket=bucket, Key=key, Body=b"1")
    body = c.get_object(Bucket=bucket, Key=key)["Body"].read()
    c.delete_object(Bucket=bucket, Key=key)
    if body != b"1":
        sys.exit(f"read back {body!r} from s3://{bucket}/{key}, expected b'1'")
    print(f"write / read / delete OK at s3://{bucket}/{key}")


def cmd_ls(args):
    bucket, prefix = parse_s3_uri(args.uri)
    n = total = 0
    for o in iter_objects(client(), bucket, prefix):
        print(f"{o['Size']:>14,}  {o['LastModified']:%Y-%m-%d %H:%M:%S}  {o['Key']}")
        n += 1
        total += o["Size"]
    print(f"{n} objects, {total:,} bytes under s3://{bucket}/{prefix}")


def cmd_put(args):
    local = Path(args.local)
    if not local.exists():
        sys.exit(f"not found: {local}")
    bucket, prefix = parse_s3_uri(args.uri)
    c = client()
    remote = {o["Key"]: o["Size"] for o in iter_objects(c, bucket, prefix)}
    sent = skipped = 0
    for path, key in upload_plan(local, prefix):
        if remote.get(key) == path.stat().st_size and not args.force:
            skipped += 1
            continue
        c.upload_file(str(path), bucket, key)
        sent += 1
    print(f"uploaded {sent}, skipped {skipped} unchanged -> s3://{bucket}/{prefix}")


def cmd_get(args):
    bucket, prefix = parse_s3_uri(args.uri)
    c = client()
    dest = Path(args.dest)
    if prefix and any(o["Key"] == prefix for o in iter_objects(c, bucket, prefix)):  # a single object
        dest.parent.mkdir(parents=True, exist_ok=True)
        c.download_file(bucket, prefix, str(dest))
        print(f"s3://{bucket}/{prefix} -> {dest}")
        return
    # List under "<prefix>/" so act_main does not also pull act_main_s2/.
    base = prefix.rstrip("/") + "/" if prefix else ""
    objs = list(iter_objects(c, bucket, base))
    if not objs:
        sys.exit(f"nothing under s3://{bucket}/{base}")
    for o in objs:
        rel = o["Key"][len(base):]
        if not rel:
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        c.download_file(bucket, o["Key"], str(out))
    print(f"{len(objs)} objects from s3://{bucket}/{base} -> {dest}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="write, read back and delete a 1-byte object under the prefix")
    p.add_argument("uri")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("ls", help="list objects under a prefix")
    p.add_argument("uri")
    p.set_defaults(fn=cmd_ls)
    p = sub.add_parser("put", help="upload a file or a directory (skips same key + same size)")
    p.add_argument("local")
    p.add_argument("uri")
    p.add_argument("--force", action="store_true", help="re-upload files that look unchanged")
    p.set_defaults(fn=cmd_put)
    p = sub.add_parser("get", help="download one object or everything under a prefix")
    p.add_argument("uri")
    p.add_argument("dest")
    p.set_defaults(fn=cmd_get)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
