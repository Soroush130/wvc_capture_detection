import os
import boto3
from botocore.exceptions import ClientError
from logger_config import get_logger

logger = get_logger(__name__)

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
AWS_S3_BUCKET_NAME = os.getenv('AWS_S3_BUCKET_NAME')
AWS_REGION = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
BUCKET = os.getenv("AWS_STORAGE_BUCKET_NAME", os.getenv("AWS_S3_BUCKET_NAME", "wvcbucket"))
PREFIX = os.getenv("AWS_LOCATION", "uploads").strip("/")


def get_s3_client():
    # Works with either IAM role (no keys) or keys from env
    return boto3.client("s3", region_name=AWS_REGION)


def _with_allowed_prefix(s3_key: str) -> str:
    s3_key = s3_key.lstrip("/")
    if not s3_key.startswith(PREFIX + "/"):
        s3_key = f"{PREFIX}/{s3_key}"
    return s3_key


def upload_to_s3(file_data: bytes, s3_key: str, content_type: str = "image/jpeg") -> tuple[bool, str]:
    """
    Upload a file to S3 under the allowed prefix and return a short-lived URL.
    """
    try:
        s3_client = get_s3_client()
        key = _with_allowed_prefix(s3_key)

        # If your bucket enforces encryption via policy, include this header. Harmless if not enforced.
        put_kwargs = {
            "Bucket": BUCKET,
            "Key": key,
            "Body": file_data,
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
        }

        s3_client.put_object(**put_kwargs)

        # Objects are private; return a presigned GET for immediate use (15 min)
        get_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=900,
        )

        logger.info(f"✅ Uploaded to S3: s3://{BUCKET}/{key}")
        return True, get_url

    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        msg = e.response.get("Error", {}).get("Message")
        logger.error(f"❌ S3 upload error ({code}): {msg}")
        return False, ""
    except Exception as e:
        logger.error(f"❌ Unexpected S3 error: {e}")
        return False, ""


def delete_from_s3(s3_key: str) -> bool:
    """Delete file from S3"""
    s3_client = get_s3_client()
    s3_key = _with_allowed_prefix(s3_key)

    try:  # ✅ اضافه کردن try-except
        s3_client.delete_object(
            Bucket=AWS_S3_BUCKET_NAME,
            Key=s3_key
        )
        logger.info(f"✅ Deleted from S3: {s3_key}")
        return True
    except Exception as e:  # ✅ handle کردن exception
        logger.error(f"❌ Failed to delete from S3: {s3_key}, Error: {e}")
        return False