"""Tests for S3Mirror and S3-aware GeneratedImageStore."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from creative_automation_cli.storage.generated_store import GeneratedImageStore
from creative_automation_cli.storage.s3_mirror import S3Mirror

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(
    *,
    list_pages: list[list[dict]] | None = None,
    download_side_effect: Exception | None = None,
) -> MagicMock:
    """Build a minimal mock boto3 S3 client."""
    client = MagicMock()

    # upload_file / download_file are simple calls
    if download_side_effect is not None:
        client.download_file.side_effect = download_side_effect

    # list_objects_v2 paginator
    paginator = MagicMock()
    pages = list_pages or []
    paginator.paginate.return_value = [{"Contents": page} for page in pages]
    client.get_paginator.return_value = paginator

    return client


def _make_s3mirror(client: MagicMock | None = None) -> S3Mirror:
    return S3Mirror(client or _make_mock_client())


def _small_rgb_image() -> Image.Image:
    return Image.new("RGB", (4, 4), color=(128, 64, 32))


# ---------------------------------------------------------------------------
# S3Mirror.from_env
# ---------------------------------------------------------------------------


def test_from_env_returns_none_when_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert S3Mirror.from_env() is None


def test_from_env_returns_none_when_only_access_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert S3Mirror.from_env() is None


def test_from_env_returns_none_when_boto3_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG")
    with patch.dict("sys.modules", {"boto3": None}):
        result = S3Mirror.from_env()
    assert result is None


def test_from_env_creates_mirror_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")

    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = MagicMock()
    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        mirror = S3Mirror.from_env()

    assert mirror is not None
    mock_boto3.client.assert_called_once()
    call_kwargs = mock_boto3.client.call_args.kwargs
    assert call_kwargs["region_name"] == "eu-west-1"


# ---------------------------------------------------------------------------
# S3Mirror primitive operations
# ---------------------------------------------------------------------------


def test_upload_file_calls_boto3(tmp_path: Path) -> None:
    client = _make_mock_client()
    mirror = _make_s3mirror(client)
    file = tmp_path / "test.png"
    file.write_bytes(b"\x89PNG")

    mirror.upload_file(file, "generated/p1/img.png")

    client.upload_file.assert_called_once_with(str(file), S3Mirror.BUCKET, "generated/p1/img.png")


def test_upload_file_swallows_exception(tmp_path: Path) -> None:
    client = _make_mock_client()
    client.upload_file.side_effect = RuntimeError("network error")
    mirror = _make_s3mirror(client)
    file = tmp_path / "test.txt"
    file.write_text("hello")
    mirror.upload_file(file, "some/key.txt")  # must not raise


def test_download_file_returns_true_on_success(tmp_path: Path) -> None:
    client = _make_mock_client()
    mirror = _make_s3mirror(client)
    dest = tmp_path / "sub" / "out.png"

    result = mirror.download_file("generated/p1/img.png", dest)

    assert result is True
    client.download_file.assert_called_once()
    assert dest.parent.exists()  # parent dir created


def test_download_file_returns_false_on_error(tmp_path: Path) -> None:
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    error = ClientError({"Error": {"Code": "NoSuchKey", "Message": ""}}, "GetObject")
    client = _make_mock_client(download_side_effect=error)
    mirror = _make_s3mirror(client)
    result = mirror.download_file("missing/key.png", tmp_path / "out.png")
    assert result is False


def test_list_keys_returns_sorted_keys() -> None:
    pages = [[{"Key": "generated/p1/20260101T000001_aaa.png"}, {"Key": "generated/p1/20260101T000003_ccc.png"}], [{"Key": "generated/p1/20260101T000002_bbb.png"}]]
    client = _make_mock_client(list_pages=pages)
    mirror = _make_s3mirror(client)

    keys = mirror.list_keys("generated/p1/")

    assert keys == [
        "generated/p1/20260101T000001_aaa.png",
        "generated/p1/20260101T000002_bbb.png",
        "generated/p1/20260101T000003_ccc.png",
    ]


def test_list_keys_returns_empty_on_error() -> None:
    client = _make_mock_client()
    client.get_paginator.side_effect = RuntimeError("auth error")
    mirror = _make_s3mirror(client)
    assert mirror.list_keys("generated/") == []


# ---------------------------------------------------------------------------
# S3Mirror domain helpers
# ---------------------------------------------------------------------------


def test_upload_output_file_uses_relative_key(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    manifest = output_root / "my-campaign" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")

    client = _make_mock_client()
    mirror = _make_s3mirror(client)
    mirror.upload_output_file(manifest, output_root)

    expected_key = "output/my-campaign/manifest.json"
    client.upload_file.assert_called_once_with(str(manifest), S3Mirror.BUCKET, expected_key)


def test_upload_output_file_logs_warning_when_not_under_root(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    import logging

    file = tmp_path / "other" / "file.json"
    file.parent.mkdir()
    file.write_text("{}")
    other_root = tmp_path / "output"
    other_root.mkdir()

    client = _make_mock_client()
    mirror = _make_s3mirror(client)
    with caplog.at_level(logging.WARNING):
        mirror.upload_output_file(file, other_root)
    client.upload_file.assert_not_called()


def test_upload_generated_image_key(tmp_path: Path) -> None:
    img_file = tmp_path / "20260225T123456_abcd1234.png"
    img_file.write_bytes(b"\x89PNG")

    client = _make_mock_client()
    mirror = _make_s3mirror(client)
    mirror.upload_generated_image(img_file, "product_1", "20260225T123456_abcd1234")

    client.upload_file.assert_called_once_with(
        str(img_file), S3Mirror.BUCKET, "generated/product_1/20260225T123456_abcd1234.png"
    )


def test_list_generated_for_product_returns_image_ids() -> None:
    pages = [[
        {"Key": "generated/p1/20260101T000001_aaa.png"},
        {"Key": "generated/p1/20260101T000002_bbb.png"},
    ]]
    client = _make_mock_client(list_pages=pages)
    mirror = _make_s3mirror(client)

    ids = mirror.list_generated_for_product("p1")
    assert ids == ["20260101T000001_aaa", "20260101T000002_bbb"]


def test_find_generated_image_key_returns_key() -> None:
    pages = [[
        {"Key": "generated/p1/20260101T000001_aaa.png"},
        {"Key": "generated/p2/20260101T000002_bbb.png"},
    ]]
    client = _make_mock_client(list_pages=pages)
    mirror = _make_s3mirror(client)

    result = mirror.find_generated_image_key("20260101T000002_bbb")
    assert result == "generated/p2/20260101T000002_bbb.png"


def test_find_generated_image_key_returns_none_when_missing() -> None:
    client = _make_mock_client(list_pages=[[]])
    mirror = _make_s3mirror(client)
    assert mirror.find_generated_image_key("nonexistent") is None


# ---------------------------------------------------------------------------
# GeneratedImageStore + S3Mirror integration
# ---------------------------------------------------------------------------


def test_generated_store_save_new_mirrors_to_s3(tmp_path: Path) -> None:
    client = _make_mock_client()
    mirror = _make_s3mirror(client)
    store = GeneratedImageStore(tmp_path, s3_mirror=mirror)

    image_id, image_path = store.save_new("product_1", _small_rgb_image())

    assert image_path.exists()
    expected_key = f"generated/product_1/{image_id}.png"
    client.upload_file.assert_called_once_with(str(image_path), S3Mirror.BUCKET, expected_key)


def test_generated_store_save_new_no_s3_when_mirror_is_none(tmp_path: Path) -> None:
    store = GeneratedImageStore(tmp_path, s3_mirror=None)
    image_id, image_path = store.save_new("product_1", _small_rgb_image())
    assert image_path.exists()  # local write still works


def test_generated_store_load_last_falls_back_to_s3(tmp_path: Path) -> None:
    """When local storage is empty, load_last_for_product should pull from S3."""
    image_id = "20260101T120000_cafebabe"

    # S3 client returns one key for product_1 and returns a real PNG on download
    def fake_download(bucket: str, key: str, dest: str) -> None:
        img = Image.new("RGB", (2, 2), color=(10, 20, 30))
        img.save(dest, format="PNG")

    client = MagicMock()
    pages = [[{"Key": f"generated/product_1/{image_id}.png"}]]
    paginator = MagicMock()
    paginator.paginate.return_value = [{"Contents": page} for page in pages]
    client.get_paginator.return_value = paginator
    client.download_file.side_effect = lambda bucket, key, dest: fake_download(bucket, key, dest)

    mirror = S3Mirror(client)
    store = GeneratedImageStore(tmp_path, s3_mirror=mirror)

    result = store.load_last_for_product("product_1")
    assert result is not None
    returned_id, returned_image = result
    assert returned_id == image_id
    assert isinstance(returned_image, Image.Image)


def test_generated_store_load_by_id_falls_back_to_s3(tmp_path: Path) -> None:
    """When local file is absent, load_by_id should download from S3."""
    image_id = "20260101T130000_deadbeef"

    def fake_download(bucket: str, key: str, dest: str) -> None:
        img = Image.new("RGB", (2, 2), color=(50, 60, 70))
        img.save(dest, format="PNG")

    client = MagicMock()
    # find_generated_image_key uses list_keys("generated/")
    pages = [[{"Key": f"generated/product_2/{image_id}.png"}]]
    paginator = MagicMock()
    paginator.paginate.return_value = [{"Contents": page} for page in pages]
    client.get_paginator.return_value = paginator
    client.download_file.side_effect = lambda bucket, key, dest: fake_download(bucket, key, dest)

    mirror = S3Mirror(client)
    store = GeneratedImageStore(tmp_path, s3_mirror=mirror)

    result = store.load_by_id(image_id)
    assert result is not None
    returned_id, returned_image = result
    assert returned_id == image_id
    assert isinstance(returned_image, Image.Image)
