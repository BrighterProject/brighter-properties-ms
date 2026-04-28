import mimetypes
import uuid

import boto3
from botocore.config import Config
from fastapi import HTTPException, UploadFile, status

from app import settings

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


async def upload_image(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported type '{file.content_type}'. Allowed: jpeg, png, webp.",
        )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 5 MB limit.",
        )

    ext = mimetypes.guess_extension(file.content_type) or ""
    if ext == ".jpe":
        ext = ".jpg"
    key = f"properties/{uuid.uuid4()}{ext}"

    _get_client().put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=data,
        ContentType=file.content_type,
    )

    return f"{settings.r2_public_url.rstrip('/')}/{key}"
