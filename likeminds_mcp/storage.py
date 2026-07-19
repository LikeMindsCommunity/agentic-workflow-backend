"""Cloudflare R2 storage — input uploads and output delivery.

Two responsibilities:
  1. INPUT  — generate presigned PUT URLs so clients upload files directly to R2,
              then download those files into the session inputs directory before
              the skill runs. Server memory never holds file bytes.
  2. OUTPUT — upload harvested deliverable files to R2 after <<<LM_DONE>>> and
              return presigned GET URLs so remote clients can download results.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import boto3
from botocore.config import Config

from . import config

# R2 key prefix for client-uploaded input files.
_INPUT_PREFIX = "inputs"


def _client():
    return boto3.client(
        "s3",
        endpoint_url=config.R2_ENDPOINT,
        aws_access_key_id=config.R2_ACCESS_KEY,
        aws_secret_access_key=config.R2_SECRET_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


# --------------------------------------------------------------------------- #
# INPUT: presigned PUT URL for direct client → R2 upload
# --------------------------------------------------------------------------- #

def upload_bytes(filename: str, data: bytes) -> str:
    """Upload raw bytes directly to R2 from the server and return the r2_key.
    Used by upload_file tool — bytes pass through the server but are not stored
    in memory beyond this call.
    """
    clean = Path(filename).name or "upload.bin"
    r2_key = f"{_INPUT_PREFIX}/{uuid.uuid4().hex}/{clean}"
    _client().put_object(Bucket=config.R2_BUCKET, Key=r2_key, Body=data)
    return r2_key


def presigned_put_url(filename: str) -> tuple[str, str]:
    """Generate a presigned PUT URL for a client to upload a file directly to R2.

    Returns (upload_url, r2_key).
      - upload_url: HTTP PUT target; client uploads raw file bytes here.
      - r2_key: opaque key to pass back via run_skill's `r2_keys` parameter.
    URL is valid for 5 minutes.
    """
    clean = Path(filename).name or "upload.bin"
    r2_key = f"{_INPUT_PREFIX}/{uuid.uuid4().hex}/{clean}"
    client = _client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": config.R2_BUCKET, "Key": r2_key},
        ExpiresIn=300,  # 5 minutes to complete the upload
    )
    return upload_url, r2_key


def download_inputs(r2_keys: list[str], inputs_dir: Path) -> list[str]:
    """Download R2 objects into the session inputs directory.

    Returns the list of filenames written. Skips any key that fails silently
    so a bad key doesn't abort the whole run.
    """
    client = _client()
    written: list[str] = []
    for key in r2_keys or []:
        filename = Path(key).name
        dest = inputs_dir / filename
        try:
            resp = client.get_object(Bucket=config.R2_BUCKET, Key=key)
            dest.write_bytes(resp["Body"].read())
            written.append(filename)
        except Exception:  # noqa: BLE001 — skip missing/expired keys
            pass
    return written


def delete_inputs(r2_keys: list[str]) -> None:
    """Delete R2 input objects after the skill has consumed them.
    Called after harvest so uploaded inputs don't linger in R2 indefinitely.
    Failures are swallowed — deletion is best-effort cleanup."""
    if not r2_keys:
        return
    client = _client()
    objects = [{"Key": k} for k in r2_keys if k]
    if objects:
        try:
            client.delete_objects(
                Bucket=config.R2_BUCKET,
                Delete={"Objects": objects, "Quiet": True},
            )
        except Exception:  # noqa: BLE001 — cleanup is best-effort
            pass


# --------------------------------------------------------------------------- #
# OUTPUT: upload harvested deliverables and return presigned GET URLs
# --------------------------------------------------------------------------- #

def upload_outputs(result_id: str, harvested: list[tuple[str, bytes]]) -> dict[str, str]:
    """Upload harvested (relative_path, bytes) files to R2.

    Returns {relative_path: presigned_get_url} for every file uploaded.
    Each URL is valid for config.R2_URL_EXPIRY seconds (default 1 hour).
    """
    client = _client()
    for name, content in harvested:
        client.put_object(
            Bucket=config.R2_BUCKET, Key=f"outputs/{result_id}/{name}", Body=content
        )
    return output_urls(result_id, [name for name, _ in harvested], client=client)


def output_urls(result_id: str, names: list[str], client=None) -> dict[str, str]:
    """Mint presigned GET URLs for an already-uploaded deliverable.

    Signing happens locally — no request reaches R2 — so this is cheap enough to call
    on every done-status snapshot. That is the point: the URLs minted when the job
    finished go stale after config.R2_URL_EXPIRY, so a client polling or revisiting a
    finished session would otherwise hand the user a dead download link.
    """
    client = client or _client()
    return {
        name: client.generate_presigned_url(
            "get_object",
            Params={"Bucket": config.R2_BUCKET, "Key": f"outputs/{result_id}/{name}"},
            ExpiresIn=config.R2_URL_EXPIRY,
        )
        for name in names
    }
