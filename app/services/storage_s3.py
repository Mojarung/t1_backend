import io
import os
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings


class S3Storage:
    def __init__(self):
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket
        if not self.bucket:
            raise RuntimeError("S3_BUCKET is not configured")
        self.client = session.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            config=Config(signature_version="s3v4"),
        )

    def build_s3_uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def parse_s3_uri(self, uri: str) -> tuple[str, str]:
        # s3://bucket/key
        if not uri.startswith("s3://"):
            raise ValueError("Not an s3 uri")
        without_scheme = uri[5:]
        bucket, key = without_scheme.split("/", 1)
        return bucket, key

    def upload_fileobj(self, fileobj, key: str, content_type: Optional[str] = None) -> str:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        self.client.upload_fileobj(fileobj, self.bucket, key, ExtraArgs=extra_args or None)
        return self.build_s3_uri(key)

    def generate_presigned_url(self, key: str, filename: Optional[str] = None, expires_in: int = 3600) -> str:
        params = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f"attachment; filename={filename}"
        url = self.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
        return url

    def get_object_bytes(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()


# Singleton accessor
_s3_storage: Optional[S3Storage] = None

def get_s3_storage() -> S3Storage:
    global _s3_storage
    if _s3_storage is None:
        _s3_storage = S3Storage()
    return _s3_storage
