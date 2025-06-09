import logging
import requests
import os
import re
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="BlobTriggerGenX")
@app.event_grid_trigger(arg_name="event")
def blob_trigger_genx(event: func.EventGridEvent):
    """
    Azure Function triggered by Event Grid when blobs are created.
    Parses the blob path to extract case names and triggers GitHub Actions workflow.
    """
    try:
        # Parse the Event Grid event
        data = event.get_json()
        blob_url = data['url']
        
        logging.info(f"Blob created: {blob_url}")
        
        # Extract container and blob path
        # URL format: https://storageaccount.blob.core.windows.net/container/path/to/blob
        url_parts = blob_url.split('/')
        container = url_parts[3]  # Container name
        blob_path = '/'.join(url_parts[4:])  # Path within container
        
        # Extract case name from blob path
        # Expected format: cases/case_name/... or inputs/case_name/...
        case_match = re.match(r'^(?:cases|inputs)/([^/]+)/', blob_path)
        if not case_match:
            logging.warning(f"Blob path {blob_path} doesn't match expected pattern. Skipping.")
            return
        
        case_name = case_match.group(1)
        logging.info(f"Detected case: {case_name} in container: {container}")
        
        # Check if this is a folder-level trigger (we want to trigger once per case folder)
        # We'll trigger only for specific file types to avoid multiple triggers
        if not any(blob_path.endswith(ext) for ext in ['.csv', '.yml', '.yaml']):
            logging.info(f"Skipping trigger for file type: {blob_path}")
            return
        
        # Prepare GitHub API call
        github_token = os.environ['GITHUB_TOKEN']
        github_repo = os.environ['GITHUB_REPO']  # e.g. "username/repo"
        workflow_id = os.environ['GITHUB_WORKFLOW_ID']  # e.g. "azure-container-apps-parallel.yml"
        
        # Prepare workflow dispatch payload
        payload = {
            "ref": "main",  # or your default branch
            "inputs": {
                "blob_container": container,
                "case_names": case_name,  # Single case for now
                "cpu_cores": "1.0",
                "memory_gb": "2.0",
                "max_parallel": "5"
            }
        }
        
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "GenX-Azure-Function"
        }
        
        # Call GitHub Actions workflow dispatch API
        url = f"https://api.github.com/repos/{github_repo}/actions/workflows/{workflow_id}/dispatches"
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 204:
            logging.info(f"Successfully triggered workflow for case: {case_name}")
        else:
            logging.error(f"Failed to trigger workflow. Status: {response.status_code}, Response: {response.text}")
            
    except Exception as e:
        logging.error(f"Error processing blob trigger: {str(e)}")
        raise
