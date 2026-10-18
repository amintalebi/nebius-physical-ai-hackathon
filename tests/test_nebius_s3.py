import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nebius_s3 import endpoint, parse_s3_uri, upload_plan  # noqa: E402


def test_parse_s3_uri():
    assert parse_s3_uri("s3://b/team/outputs") == ("b", "team/outputs")
    assert parse_s3_uri("s3://b") == ("b", "")
    assert parse_s3_uri("s3://b/") == ("b", "")
    with pytest.raises(ValueError):
        parse_s3_uri("b/team")
    with pytest.raises(ValueError):
        parse_s3_uri("s3:///team")


def test_endpoint_follows_region(monkeypatch):
    monkeypatch.delenv("NEBIUS_S3_ENDPOINT", raising=False)
    monkeypatch.setenv("NEBIUS_REGION", "us-central1")
    assert endpoint() == "https://storage.us-central1.nebius.cloud"
    monkeypatch.setenv("NEBIUS_S3_ENDPOINT", "https://example.test")
    assert endpoint() == "https://example.test"


def test_upload_plan_directory_keeps_layout(tmp_path):
    (tmp_path / "ckpt/pretrained_model").mkdir(parents=True)
    (tmp_path / "ckpt/pretrained_model/model.safetensors").write_bytes(b"x")
    (tmp_path / "ckpt/train.log").write_text("l")
    plan = upload_plan(tmp_path / "ckpt", "team/outputs/act_main/")
    assert [k for _, k in plan] == [
        "team/outputs/act_main/pretrained_model/model.safetensors",
        "team/outputs/act_main/train.log",
    ]
    assert [k for _, k in upload_plan(tmp_path / "ckpt", "")] == ["pretrained_model/model.safetensors", "train.log"]


def test_upload_plan_single_file(tmp_path):
    f = tmp_path / "manifest.json"
    f.write_text("{}")
    assert upload_plan(f, "team/manifest.json") == [(f, "team/manifest.json")]
    assert upload_plan(f, "team/") == [(f, "team/manifest.json")]
    assert upload_plan(f, "") == [(f, "manifest.json")]
