#!/usr/bin/env python3
"""
Enhanced GenX runner script that can download cases from Azure Blob Storage,
run GenX optimization, and upload results back to blob storage.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import json
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GenXCaseRunner:
    def __init__(self):
        self.case_name = os.environ.get('GENX_CASE_NAME')
        self.blob_path = os.environ.get('GENX_BLOB_PATH')
        self.storage_account = os.environ.get('AZURE_STORAGE_ACCOUNT', 'genxstorage')
        self.storage_key = os.environ.get('AZURE_STORAGE_KEY')
        self.storage_connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        
        # Container names
        self.input_container = os.environ.get('GENX_INPUT_CONTAINER', 'cases')
        self.output_container = os.environ.get('GENX_OUTPUT_CONTAINER', 'results')
        
        # Setup blob service client
        self.blob_service_client = self._setup_blob_client()
        
    def _setup_blob_client(self):
        """Setup Azure Blob Storage client with available credentials."""
        try:
            if self.storage_connection_string:
                return BlobServiceClient.from_connection_string(self.storage_connection_string)
            elif self.storage_key:
                account_url = f"https://{self.storage_account}.blob.core.windows.net"
                return BlobServiceClient(account_url=account_url, credential=self.storage_key)
            else:
                # Try managed identity
                account_url = f"https://{self.storage_account}.blob.core.windows.net"
                credential = DefaultAzureCredential()
                return BlobServiceClient(account_url=account_url, credential=credential)
        except Exception as e:
            logger.error(f"Failed to setup blob client: {e}")
            return None

    def download_case_data(self):
        """Download case data from blob storage."""
        if not self.case_name:
            logger.error("No case name specified")
            return False
            
        if not self.blob_service_client:
            logger.error("Blob service client not available")
            return False
            
        try:
            logger.info(f"Downloading case data for: {self.case_name}")
            
            # Create local case directory
            case_dir = Path(f"/app/cases/{self.case_name}")
            case_dir.mkdir(parents=True, exist_ok=True)
            
            # Download all blobs for this case
            container_client = self.blob_service_client.get_container_client(self.input_container)
            
            # List blobs with case prefix
            blobs = container_client.list_blobs(name_starts_with=self.case_name)
            downloaded_files = []
            
            for blob in blobs:
                # Skip if this is a results file
                if '/results/' in blob.name:
                    continue
                    
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.input_container, 
                    blob=blob.name
                )
                
                # Create local file path
                local_file_path = Path(f"/app/cases/{blob.name}")
                local_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Download blob
                with open(local_file_path, 'wb') as file:
                    blob_data = blob_client.download_blob()
                    file.write(blob_data.readall())
                
                downloaded_files.append(str(local_file_path))
                logger.info(f"Downloaded: {blob.name}")
            
            if not downloaded_files:
                logger.warning(f"No files downloaded for case: {self.case_name}")
                return False
                
            logger.info(f"Successfully downloaded {len(downloaded_files)} files for case {self.case_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading case data: {e}")
            return False

    def run_genx_optimization(self):
        """Run GenX optimization on the downloaded case."""
        try:
            case_path = f"/app/cases/{self.case_name}"
            
            # Check if case directory exists
            if not Path(case_path).exists():
                logger.error(f"Case directory not found: {case_path}")
                return False
            
            logger.info(f"Running GenX optimization for case: {self.case_name}")
            logger.info(f"Case path: {case_path}")
            
            # Change to app directory and run Julia
            os.chdir("/app")
            
            # Run GenX with the case
            cmd = [
                "julia", 
                "--project=.", 
                "Run.jl", 
                case_path
            ]
            
            logger.info(f"Executing command: {' '.join(cmd)}")
            
            # Run the optimization
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            # Log output
            if result.stdout:
                logger.info("GenX stdout:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"  {line}")
            
            if result.stderr:
                logger.warning("GenX stderr:")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        logger.warning(f"  {line}")
            
            if result.returncode == 0:
                logger.info("GenX optimization completed successfully")
                return True
            else:
                logger.error(f"GenX optimization failed with return code: {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("GenX optimization timed out")
            return False
        except Exception as e:
            logger.error(f"Error running GenX optimization: {e}")
            return False

    def upload_results(self):
        """Upload results back to blob storage."""
        if not self.blob_service_client:
            logger.error("Blob service client not available")
            return False
            
        try:
            results_dir = Path(f"/app/cases/{self.case_name}/results")
            
            if not results_dir.exists():
                logger.error(f"Results directory not found: {results_dir}")
                return False
            
            logger.info(f"Uploading results for case: {self.case_name}")
            
            uploaded_files = []
            
            # Upload all files in results directory
            for file_path in results_dir.rglob('*'):
                if file_path.is_file():
                    # Create blob name with case prefix
                    relative_path = file_path.relative_to(results_dir)
                    blob_name = f"{self.case_name}/results/{relative_path}"
                    blob_name = blob_name.replace('\\', '/')
                    
                    # Upload file
                    blob_client = self.blob_service_client.get_blob_client(
                        container=self.output_container, 
                        blob=blob_name
                    )
                    
                    with open(file_path, 'rb') as data:
                        blob_client.upload_blob(data, overwrite=True)
                    
                    uploaded_files.append(blob_name)
                    logger.info(f"Uploaded: {blob_name}")
            
            # Create a summary metadata file
            summary = {
                "case_name": self.case_name,
                "completed_at": datetime.now().isoformat(),
                "files_uploaded": len(uploaded_files),
                "files": uploaded_files,
                "status": "completed"
            }
            
            # Upload summary file
            summary_blob_name = f"{self.case_name}/results/_summary.json"
            summary_blob_client = self.blob_service_client.get_blob_client(
                container=self.output_container,
                blob=summary_blob_name
            )
            
            summary_data = json.dumps(summary, indent=2).encode('utf-8')
            summary_blob_client.upload_blob(summary_data, overwrite=True)
            
            logger.info(f"Successfully uploaded {len(uploaded_files)} result files for case {self.case_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading results: {e}")
            return False

    def run_fallback_example(self):
        """Run the fallback three-zone example if no case is specified."""
        try:
            logger.info("Running fallback three-zone example")
            
            os.chdir("/app")
            cmd = [
                "julia", 
                "--project=.", 
                "Run.jl", 
                "./example_systems/1_three_zones"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            
            if result.stdout:
                logger.info("Example output:")
                for line in result.stdout.split('\n')[-20:]:  # Last 20 lines
                    if line.strip():
                        logger.info(f"  {line}")
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error running fallback example: {e}")
            return False

    def run(self):
        """Main execution method."""
        logger.info("Starting GenX Case Runner")
        logger.info(f"Case name: {self.case_name}")
        logger.info(f"Blob path: {self.blob_path}")
        logger.info(f"Storage account: {self.storage_account}")
        
        # If no case name specified, run fallback example
        if not self.case_name:
            logger.info("No case name specified, running fallback example")
            success = self.run_fallback_example()
            sys.exit(0 if success else 1)
        
        # Download case data
        if not self.download_case_data():
            logger.error("Failed to download case data")
            sys.exit(1)
        
        # Run optimization
        if not self.run_genx_optimization():
            logger.error("GenX optimization failed")
            sys.exit(1)
        
        # Upload results
        if not self.upload_results():
            logger.error("Failed to upload results")
            sys.exit(1)
        
        logger.info("GenX case processing completed successfully")


if __name__ == "__main__":
    runner = GenXCaseRunner()
    runner.run()
