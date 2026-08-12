from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from loguru import logger

from app.config import config

_REQUIRED_KEYS = (
    "S3_ENDPOINT_URL",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "S3_BUCKET",
)

_client = None


def _ensure_configured() -> None:
    missing = [name for name in _REQUIRED_KEYS if not getattr(config, name, "")]
    if missing:
        raise RuntimeError(
            "S3 is enabled but missing required configuration: " + ", ".join(missing)
        )


def get_client():
    """创建并返回 boto3 S3 client，单例"""
    global _client
    if _client is None:
        _ensure_configured()
        _client = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT_URL,
            aws_access_key_id=config.S3_ACCESS_KEY_ID,
            aws_secret_access_key=config.S3_SECRET_ACCESS_KEY,
            region_name=config.S3_REGION,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
        )
    return _client


def is_enabled() -> bool:
    """S3 是否启用"""
    return config.S3_STORAGE_ENABLED


def upload_bytes(key: str, data: bytes, content_type: Optional[str] = None) -> None:
    """上传字节对象到 S3"""
    extra = {"ContentType": content_type} if content_type else {}
    get_client().put_object(Bucket=config.S3_BUCKET, Key=key, Body=data, **extra)
    logger.debug(f"Uploaded object to S3: {key} ({len(data)} bytes)")


def exists(key: str) -> bool:
    """检查文件对象是否已存在"""
    try:
        get_client().head_object(Bucket=config.S3_BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code", "") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def presign_get(
    key: str,
    *,
    expires: Optional[int] = None,
    download_filename: Optional[str] = None,
    content_type: Optional[str] = None,
) -> str:
    """生成 presigned GET URL，并把 host 换成公网 CDN 域名返回

    Args:
        key: 对象键
        download_filename: 不为空则附加 Content-Disposition: attachment
        content_type: 覆盖响应的 Content-Type
    """
    params = {"Bucket": config.S3_BUCKET, "Key": key}
    if download_filename:
        params["ResponseContentDisposition"] = (
            f"attachment; filename*=UTF-8''{quote(download_filename, safe='')}"
        )
    if content_type:
        params["ResponseContentType"] = content_type

    url = get_client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires if expires is not None else 300,
    )
    return _swap_host(url)


def _swap_host(url: str) -> str:
    """
    把 presigned URL 的 scheme+host 换成 CDN 域名，path/query 原样保留
    未配置 S3_CDN_BASE_URL 时原样返回
    """
    if not config.S3_CDN_BASE_URL:
        return url
    src = urlsplit(url)
    cdn = urlsplit(config.S3_CDN_BASE_URL)
    return urlunsplit((cdn.scheme, cdn.netloc, src.path, src.query, src.fragment))


def list_objects(prefix: str) -> list[dict]:
    """列出 prefix 下全部对象"""
    client = get_client()
    paginator = client.get_paginator("list_objects_v2")
    res: list[dict] = []
    for page in paginator.paginate(Bucket=config.S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            res.append(
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
            )
    return res


def stat_prefix(prefix: str) -> dict:
    """遍历 prefix 累加大小与数量"""
    client = get_client()
    paginator = client.get_paginator("list_objects_v2")
    size = 0
    count = 0
    for page in paginator.paginate(Bucket=config.S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            size += obj["Size"]  # bytes
            count += 1
    return {"size": size, "count": count}


def delete_keys(keys: list[str]) -> int:
    """按 key 批量删除，每批最多 1000，返回成功删除数量"""
    if not keys:
        return 0
    client = get_client()
    deleted = 0
    for i in range(0, len(keys), 1000):
        batch = [{"Key": k} for k in keys[i: i + 1000]]
        resp = client.delete_objects(Bucket=config.S3_BUCKET, Delete={"Objects": batch})
        deleted += len(resp.get("Deleted", []))
        errors = resp.get("Errors", [])
        if errors:
            logger.warning(f"Failed to delete {len(errors)} objects in batch: {errors[:3]}")
    return deleted


def delete_prefix(prefix: str) -> int:
    """删除 prefix 下全部对象，返回删除数量"""
    keys = [o["key"] for o in list_objects(prefix)]
    return delete_keys(keys)
