import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

BUCKET_NAME = "trilio-backups"
MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"


def get_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


def ensure_bucket(client):
    try:
        client.head_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' already exists.")
    except ClientError:
        client.create_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' created.")


def compute_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def upload_action(client, path):
    if not os.path.exists(path):
        print(f"Error: path '{path}' does not exist.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    prefix = f"backups/{timestamp}/"
    manifest = {"prefix": prefix, "files": []}

    if os.path.isfile(path):
        files_to_upload = [path]
        base_dir = os.path.dirname(path) or "."
    else:
        files_to_upload = []
        for root, _, files in os.walk(path):
            for name in files:
                files_to_upload.append(os.path.join(root, name))
        base_dir = path

    for file_path in files_to_upload:
        md5sum = compute_md5(file_path)
        rel_path = os.path.relpath(file_path, base_dir)
        key = f"{prefix}{rel_path}"

        client.upload_file(
            file_path,
            BUCKET_NAME,
            key,
            ExtraArgs={"Metadata": {"md5": md5sum}},
        )
        print(f"Uploaded {file_path} -> {key} (md5={md5sum})")
        manifest["files"].append({"key": key, "md5": md5sum})

    manifest_key = f"{prefix}manifest.json"
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    client.put_object(Bucket=BUCKET_NAME, Key=manifest_key, Body=manifest_bytes)
    print(f"Manifest written to {manifest_key}")


def verify_action(client, prefix):
    paginator = client.get_paginator("list_objects_v2")
    all_pass = True
    file_count = 0

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("manifest.json"):
                continue

            file_count += 1
            head = client.head_object(Bucket=BUCKET_NAME, Key=key)
            stored_md5 = head.get("Metadata", {}).get("md5")

            response = client.get_object(Bucket=BUCKET_NAME, Key=key)
            body = response["Body"].read()
            actual_md5 = hashlib.md5(body).hexdigest()

            if stored_md5 == actual_md5:
                print(f"PASS: {key} (md5={actual_md5})")
            else:
                all_pass = False
                print(f"FAIL: {key} (stored={stored_md5}, actual={actual_md5})")

    if file_count == 0:
        print(f"No files found under prefix '{prefix}'.")
        return

    status = "PASS" if all_pass else "FAIL"
    print(f"Overall integrity status: {status} ({file_count} file(s) checked)")


def list_action(client):
    paginator = client.get_paginator("list_objects_v2")
    prefixes = {}

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix="backups/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            parts = key.split("/")
            if len(parts) < 2:
                continue
            prefix = f"{parts[0]}/{parts[1]}/"
            stats = prefixes.setdefault(prefix, {"count": 0, "size": 0})
            stats["count"] += 1
            stats["size"] += obj["Size"]

    if not prefixes:
        print("No backup prefixes found.")
        return

    for prefix in sorted(prefixes):
        stats = prefixes[prefix]
        print(f"{prefix} - {stats['count']} object(s), {stats['size']} bytes total")


def delete_action(client, prefix):
    paginator = client.get_paginator("list_objects_v2")
    keys_to_delete = []

    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys_to_delete.append({"Key": obj["Key"]})

    if not keys_to_delete:
        print(f"No objects found under prefix '{prefix}'.")
        return

    client.delete_objects(Bucket=BUCKET_NAME, Delete={"Objects": keys_to_delete})
    print(f"Deleted {len(keys_to_delete)} object(s) under prefix '{prefix}'.")


def main():
    parser = argparse.ArgumentParser(description="Backup Target Simulator")
    parser.add_argument("--action", required=True, choices=["upload", "verify", "list", "delete"])
    parser.add_argument("--path", help="File or directory to upload")
    parser.add_argument("--prefix", help="Prefix for verify/list/delete")
    args = parser.parse_args()

    client = get_client()
    ensure_bucket(client)

    if args.action == "upload":
        if not args.path:
            print("Error: --path is required for upload action.")
            return
        upload_action(client, args.path)
    elif args.action == "verify":
        if not args.prefix:
            print("Error: --prefix is required for verify action.")
            return
        verify_action(client, args.prefix)
    elif args.action == "list":
        list_action(client)
    elif args.action == "delete":
        if not args.prefix:
            print("Error: --prefix is required for delete action.")
            return
        delete_action(client, args.prefix)


if __name__ == "__main__":
    main()
