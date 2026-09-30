# Assignment 3 - S3/Object Storage - Backup Target Simulator

A Python-based backup target simulator that uses S3-compatible object storage (SeaweedFS) to store, verify, list, and delete backups.

## Backend

This project uses SeaweedFS as a local S3-compatible storage backend, running in Docker (MinIO was used originally but its images are no longer available on Docker Hub/Quay.io, so SeaweedFS was used as a substitute).

- Endpoint: http://localhost:9000
- Access Key: minioadmin
- Secret Key: minioadmin
- Bucket: trilio-backups

## Setup

1. Install dependencies:
 pip install -r requirements.txt

2. Make sure the SeaweedFS container is running:
 docker start seaweed-backup

## Usage

Upload a file or directory:
 python3 backup_target.py --action upload --path <file_or_folder>

Verify a backup:
 python3 backup_target.py --action verify --prefix <backup_prefix>

List all backups:
 python3 backup_target.py --action list

Delete a backup:
 python3 backup_target.py --action delete --prefix <backup_prefix>

## Features

- Automatic bucket creation
- Recursive file/directory upload with MD5 checksum stored as S3 metadata
- manifest.json generated for every backup
- Integrity verification (PASS/FAIL) by re-computing and comparing MD5
- Listing of all backup prefixes with object count and total size
- Batch deletion of all objects under a prefix
