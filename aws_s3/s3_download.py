# s3_download.py
import os
import tempfile
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from aws_s3.s3_utils import _with_allowed_prefix
from logger_config import get_logger

logger = get_logger(__name__)

AWS_REGION = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
BUCKET = os.getenv("AWS_STORAGE_BUCKET_NAME", os.getenv("AWS_S3_BUCKET_NAME", "wvcbucket"))
PREFIX = os.getenv("AWS_LOCATION", "uploads").strip("/")


def get_s3_client():
    return boto3.client("s3", region_name=AWS_REGION)


def download_from_s3(s3_key: str) -> Optional[str]:
    try:
        s3_client = get_s3_client()

        full_key = _with_allowed_prefix(s3_key)

        suffix = os.path.splitext(s3_key)[1] or '.jpg'
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name
        temp_file.close()

        s3_client.download_file(
            Bucket=BUCKET,
            Key=full_key,
            Filename=temp_path
        )

        logger.info(f"📥 Downloaded from S3: s3://{BUCKET}/{full_key} -> {temp_path}")
        return temp_path

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))

        logger.error(f"❌ S3 download error ({error_code}): {error_msg}")
        logger.error(f"   Bucket: {BUCKET}")
        logger.error(f"   Key: {_with_allowed_prefix(s3_key)}")

        if error_code == '403' or error_code == 'Forbidden':
            logger.error("❌ Permission denied. Check:")
            logger.error("   1. IAM role has s3:GetObject permission")
            logger.error("   2. Bucket policy allows access")
            logger.error("   3. File exists in S3")
        elif error_code == '404' or error_code == 'NoSuchKey':
            logger.error(f"❌ File not found in S3: {_with_allowed_prefix(s3_key)}")

        return None

    except Exception as e:
        logger.error(f"❌ Unexpected download error: {e}")
        return None


def get_s3_url(s3_key: str) -> str:
    full_key = _with_allowed_prefix(s3_key)
    return f"https://{BUCKET}.s3.{AWS_REGION}.amazonaws.com/{full_key}"


def get_presigned_url(s3_key: str, expires_in: int = 900) -> Optional[str]:
    try:
        s3_client = get_s3_client()
        full_key = _with_allowed_prefix(s3_key)

        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET, 'Key': full_key},
            ExpiresIn=expires_in
        )

        return url

    except Exception as e:
        logger.error(f"❌ Error generating presigned URL: {e}")
        return None
