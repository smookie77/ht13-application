import logging
from functools import cached_property

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from .base import StorageError

logger = logging.getLogger(__name__)


class R2TicketStorage:
    """Cloudflare R2 over the S3 API.

    Chosen over S3 because egress is free: every buyer downloads their ticket at
    least once, often from a phone at the door, and R2 does not bill for that.
    It speaks the S3 protocol, so boto3 works unchanged and moving to S3 later
    is a settings change.

    The bucket is private. Reads are served through short-lived presigned URLs,
    never public objects.
    """

    def __init__(self, bucket: str | None = None):
        self.bucket = bucket or settings.R2_BUCKET_NAME
        if not self.bucket:
            raise StorageError("R2_BUCKET_NAME is not configured.")

    @cached_property
    def client(self):
        if not (settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY):
            raise StorageError("R2 credentials are not configured.")
        return boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            # R2 ignores regions but boto3 insists on one; v4 signing is required.
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def save(self, key: str, content: bytes, content_type: str = "application/pdf") -> str:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("R2 upload failed for %s", key)
            raise StorageError("Could not store the ticket.") from exc
        return key

    def read(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Could not read object {key}.") from exc

    def signed_url(self, key: str, expires_in: int = 300) -> str | None:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Could not presign %s", key)
            raise StorageError("Could not produce a download link.") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Could not delete object {key}.") from exc
