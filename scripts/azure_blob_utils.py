#!/usr/bin/env python3
"""
Utility script for Azure Blob Storage operations for GenX workflows.
This script can be used for testing blob upload/download operations.
"""

import os
import argparse
from azure.storage.blob import BlobServiceClient
from pathlib import Path
import sys
from datetime import datetime

def upload_directory(blob_service_client, container_name, local_directory, blob_prefix=""):
    """Upload a directory to Azure Blob Storage."""
    local_path = Path(local_directory)
    if not local_path.exists():
        print(f"Error: Local directory {local_directory} does not exist")
        return False
    
    uploaded_files = []
    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            # Create blob name maintaining directory structure
            relative_path = file_path.relative_to(local_path)
            blob_name = f"{blob_prefix}/{relative_path}" if blob_prefix else str(relative_path)
            blob_name = blob_name.replace("\\", "/")  # Ensure forward slashes
            
            try:
                blob_client = blob_service_client.get_blob_client(
                    container=container_name, blob=blob_name
                )
                
                with open(file_path, 'rb') as data:
                    blob_client.upload_blob(data, overwrite=True)
                
                uploaded_files.append(blob_name)
                print(f"Uploaded: {blob_name}")
                
            except Exception as e:
                print(f"Error uploading {file_path}: {e}")
                return False
    
    print(f"Successfully uploaded {len(uploaded_files)} files")
    return True

def download_directory(blob_service_client, container_name, blob_prefix, local_directory):
    """Download blobs with a prefix to a local directory."""
    local_path = Path(local_directory)
    local_path.mkdir(parents=True, exist_ok=True)
    
    container_client = blob_service_client.get_container_client(container_name)
    downloaded_files = []
    
    try:
        blob_list = container_client.list_blobs(name_starts_with=blob_prefix)
        
        for blob in blob_list:
            # Remove prefix from blob name to get relative path
            if blob_prefix and blob.name.startswith(blob_prefix):
                relative_path = blob.name[len(blob_prefix):].lstrip('/')
            else:
                relative_path = blob.name
            
            local_file_path = local_path / relative_path
            local_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            blob_client = blob_service_client.get_blob_client(
                container=container_name, blob=blob.name
            )
            
            with open(local_file_path, 'wb') as download_file:
                download_file.write(blob_client.download_blob().readall())
            
            downloaded_files.append(local_file_path)
            print(f"Downloaded: {blob.name} -> {local_file_path}")
    
    except Exception as e:
        print(f"Error downloading files: {e}")
        return False
    
    print(f"Successfully downloaded {len(downloaded_files)} files")
    return True

def list_blobs(blob_service_client, container_name, prefix=""):
    """List blobs in a container."""
    container_client = blob_service_client.get_container_client(container_name)
    
    try:
        blob_list = container_client.list_blobs(name_starts_with=prefix)
        blobs = []
        
        print(f"Blobs in container '{container_name}' with prefix '{prefix}':")
        for blob in blob_list:
            blobs.append(blob.name)
            print(f"  - {blob.name} (Size: {blob.size} bytes, Modified: {blob.last_modified})")
        
        return blobs
    
    except Exception as e:
        print(f"Error listing blobs: {e}")
        return []

def trigger_github_workflow(repo_owner, repo_name, github_token, container, input_folder, case_name):
    """Trigger the GitHub workflow via repository dispatch."""
    import requests
    
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/dispatches"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    payload = {
        "event_type": "blob-upload",
        "client_payload": {
            "container": container,
            "input_folder": input_folder,
            "case_name": case_name,
            "triggered_at": datetime.now().isoformat()
        }
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 204:
        print(f"Successfully triggered GitHub workflow for {repo_owner}/{repo_name}")
        return True
    else:
        print(f"Error triggering workflow: {response.status_code} - {response.text}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Azure Blob Storage utilities for GenX")
    parser.add_argument("action", choices=["upload", "download", "list", "trigger"], 
                       help="Action to perform")
    parser.add_argument("--account-name", required=True, help="Azure Storage Account name")
    parser.add_argument("--account-key", help="Azure Storage Account key")
    parser.add_argument("--connection-string", help="Azure Storage connection string")
    parser.add_argument("--container", required=True, help="Container name")
    parser.add_argument("--local-path", help="Local directory path")
    parser.add_argument("--blob-prefix", default="", help="Blob prefix/folder")
    parser.add_argument("--case-name", help="Case name for GenX run")
    
    # GitHub workflow trigger options
    parser.add_argument("--github-token", help="GitHub personal access token")
    parser.add_argument("--repo-owner", help="GitHub repository owner")
    parser.add_argument("--repo-name", help="GitHub repository name")
    
    args = parser.parse_args()
    
    # Create blob service client
    if args.connection_string:
        blob_service_client = BlobServiceClient.from_connection_string(args.connection_string)
    elif args.account_key:
        account_url = f"https://{args.account_name}.blob.core.windows.net"
        blob_service_client = BlobServiceClient(account_url=account_url, credential=args.account_key)
    else:
        print("Error: Either --account-key or --connection-string is required")
        sys.exit(1)
    
    # Perform action
    if args.action == "upload":
        if not args.local_path:
            print("Error: --local-path is required for upload")
            sys.exit(1)
        success = upload_directory(blob_service_client, args.container, args.local_path, args.blob_prefix)
        
    elif args.action == "download":
        if not args.local_path:
            print("Error: --local-path is required for download")
            sys.exit(1)
        success = download_directory(blob_service_client, args.container, args.blob_prefix, args.local_path)
        
    elif args.action == "list":
        blobs = list_blobs(blob_service_client, args.container, args.blob_prefix)
        success = len(blobs) >= 0  # Success if we can list (even if empty)
        
    elif args.action == "trigger":
        if not all([args.github_token, args.repo_owner, args.repo_name, args.case_name]):
            print("Error: --github-token, --repo-owner, --repo-name, and --case-name are required for trigger")
            sys.exit(1)
        success = trigger_github_workflow(
            args.repo_owner, args.repo_name, args.github_token, 
            args.container, args.blob_prefix, args.case_name
        )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

