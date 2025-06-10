import azure.functions as func
import logging
import json
import os
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.containerinstance import ContainerInstanceManagementClient
from azure.containerinstance.models import (
    ContainerGroup, Container, ContainerGroupRestartPolicy,
    ResourceRequests, ResourceRequirements, ContainerPort,
    ImageRegistryCredential, EnvironmentVariable, VolumeMount, Volume,
    AzureFileVolume, OperatingSystemTypes
)
import uuid
import time

app = func.FunctionApp()

@app.event_grid_trigger(arg_name="azeventgrid")
def blob_trigger(azeventgrid: func.EventGridEvent):
    """
    Azure Function triggered by Event Grid when blobs are uploaded to storage.
    Processes GenX case uploads and triggers container processing.
    """
    logging.info('GenX Event Grid trigger function processed an event')
    
    # Parse the Event Grid event
    event_data = azeventgrid.get_json()
    logging.info(f'Event data: {json.dumps(event_data, indent=2)}')
    
    # Extract blob information
    blob_url = event_data.get('url', '')
    event_type = azeventgrid.event_type
    
    # Only process blob creation events
    if event_type != 'Microsoft.Storage.BlobCreated':
        logging.info(f'Ignoring event type: {event_type}')
        return
    
    # Parse blob path
    blob_path = blob_url.split('/')[-1]  # Get the blob name
    container_name = blob_url.split('/')[-2]  # Get container name
    
    logging.info(f'Processing blob: {blob_path} in container: {container_name}')
    
    # Check if this is a GenX case upload (look for specific patterns)
    if not is_genx_case(blob_path):
        logging.info(f'Blob {blob_path} is not a GenX case, skipping')
        return
    
    # Extract case name from blob path
    case_name = extract_case_name(blob_path)
    logging.info(f'Detected GenX case: {case_name}')
    
    try:
        # Create and run container instance for GenX processing
        container_name = f"genx-{case_name}-{uuid.uuid4().hex[:8]}"
        success = create_genx_container(container_name, case_name, blob_path)
        
        if success:
            logging.info(f'Successfully created container {container_name} for case {case_name}')
        else:
            logging.error(f'Failed to create container for case {case_name}')
            
    except Exception as e:
        logging.error(f'Error processing GenX case {case_name}: {str(e)}')


def is_genx_case(blob_path: str) -> bool:
    """
    Check if the uploaded blob represents a GenX case.
    This can be customized based on your naming conventions.
    """
    # Look for typical GenX case indicators
    genx_indicators = [
        'Run.jl',
        'Generators_data.csv',
        'Load_data.csv',
        'Fuels_data.csv',
        'genx_settings.yml'
    ]
    
    # Check if blob path contains GenX case files
    for indicator in genx_indicators:
        if indicator.lower() in blob_path.lower():
            return True
    
    # Also check if it's in a case directory structure
    if '/case/' in blob_path or blob_path.startswith('case_'):
        return True
        
    return False


def extract_case_name(blob_path: str) -> str:
    """
    Extract case name from blob path.
    Customize this based on your blob naming convention.
    """
    # Remove file extension and path separators
    parts = blob_path.replace('\\', '/').split('/')
    
    # Look for case directory or use first meaningful part
    for part in parts:
        if part and part not in ['cases', 'data', 'inputs']:
            # Clean up the case name
            case_name = part.replace('.csv', '').replace('.yml', '').replace('.jl', '')
            # Remove common suffixes/prefixes
            case_name = case_name.replace('genx_', '').replace('_data', '').replace('_settings', '')
            return case_name[:50]  # Limit length for container naming
    
    # Fallback to timestamp-based name
    return f"case_{int(time.time())}"


def create_genx_container(container_name: str, case_name: str, blob_path: str) -> bool:
    """
    Create an Azure Container Instance to process the GenX case.
    """
    try:
        # Get configuration from environment variables
        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        resource_group = os.environ.get('AZURE_RESOURCE_GROUP', 'genx-rg')
        registry_name = os.environ.get('AZURE_REGISTRY_NAME', 'genxjlregistry')
        storage_account = os.environ.get('AZURE_STORAGE_ACCOUNT', 'genxstorage')
        
        # Initialize Azure clients
        credential = DefaultAzureCredential()
        aci_client = ContainerInstanceManagementClient(credential, subscription_id)
        
        # Get registry credentials
        registry_server = f"{registry_name}.azurecr.io"
        registry_username = os.environ.get('AZURE_REGISTRY_USERNAME')
        registry_password = os.environ.get('AZURE_REGISTRY_PASSWORD')
        
        # Define environment variables for the container
        environment_vars = [
            EnvironmentVariable(name="GENX_CASE_NAME", value=case_name),
            EnvironmentVariable(name="GENX_BLOB_PATH", value=blob_path),
            EnvironmentVariable(name="AZURE_STORAGE_ACCOUNT", value=storage_account),
            EnvironmentVariable(name="AZURE_STORAGE_KEY", value=os.environ.get('AZURE_STORAGE_KEY')),
            EnvironmentVariable(name="GENX_PRECOMPILE", value="false"),
            EnvironmentVariable(name="JULIA_NUM_THREADS", value="auto"),
        ]
        
        # Get image tag from environment (commit SHA)
        image_tag = os.environ.get('GENX_IMAGE_TAG', 'latest')
        
        # Define container configuration
        container = Container(
            name=container_name,
            image=f"{registry_server}/genx-jl:{image_tag}",
            resources=ResourceRequirements(
                requests=ResourceRequests(
                    memory_in_gb=8.0,
                    cpu=4.0
                )
            ),
            environment_variables=environment_vars,
            command=[
                "/bin/bash", "-c",
                """
                # Download case data from blob storage
                echo "Downloading case data for: $GENX_CASE_NAME"
                python3 -c "
import os
from azure.storage.blob import BlobServiceClient
from pathlib import Path

# Setup blob client
account_name = os.environ['AZURE_STORAGE_ACCOUNT']
account_key = os.environ['AZURE_STORAGE_KEY']
account_url = f'https://{account_name}.blob.core.windows.net'
blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)

# Download case data
case_name = os.environ['GENX_CASE_NAME']
container_name = 'cases'
local_case_dir = f'/app/cases/{case_name}'
Path(local_case_dir).mkdir(parents=True, exist_ok=True)

# Download all blobs for this case
container_client = blob_service_client.get_container_client(container_name)
blobs = container_client.list_blobs(name_starts_with=case_name)

for blob in blobs:
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob.name)
    local_file_path = f'/app/cases/{blob.name}'
    Path(local_file_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(local_file_path, 'wb') as file:
        blob_data = blob_client.download_blob()
        file.write(blob_data.readall())
    print(f'Downloaded: {blob.name}')
"
                
                # Run GenX optimization
                echo "Running GenX optimization for case: $GENX_CASE_NAME"
                cd /app
                julia --project=. Run.jl ./cases/$GENX_CASE_NAME
                
                # Upload results back to blob storage
                echo "Uploading results for case: $GENX_CASE_NAME"
                python3 -c "
import os
from azure.storage.blob import BlobServiceClient
from pathlib import Path

# Setup blob client
account_name = os.environ['AZURE_STORAGE_ACCOUNT']
account_key = os.environ['AZURE_STORAGE_KEY']
account_url = f'https://{account_name}.blob.core.windows.net'
blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)

# Upload results from both results/ and TDR_results/ directories
case_name = os.environ['GENX_CASE_NAME']
case_dir = Path(f'/app/cases/{case_name}')

# Define result directories to upload
result_dirs = ['results', 'TDR_results']
uploaded_files = 0

for result_subdir in result_dirs:
    results_dir = case_dir / result_subdir
    
    if results_dir.exists():
        print(f'Uploading {result_subdir} for case: {case_name}')
        container_name = 'results'
        
        for file_path in results_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(case_dir)
                blob_name = f'{case_name}/{relative_path}'.replace('\\\\', '/')
                
                blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
                
                with open(file_path, 'rb') as data:
                    blob_client.upload_blob(data, overwrite=True)
                print(f'Uploaded: {blob_name}')
                uploaded_files += 1
    else:
        print(f'Directory {result_subdir} not found for case: {case_name}')

if uploaded_files > 0:
    print(f'Successfully uploaded {uploaded_files} result files for case: {case_name}')
else:
    print(f'No result files found for case: {case_name}')
    exit(1)
"
                
                echo "GenX processing completed successfully for case: $GENX_CASE_NAME"
                """
            ]
        )
        
        # Registry credentials
        registry_credentials = []
        if registry_username and registry_password:
            registry_credentials = [
                ImageRegistryCredential(
                    server=registry_server,
                    username=registry_username,
                    password=registry_password
                )
            ]
        
        # Create container group
        container_group = ContainerGroup(
            location=os.environ.get('AZURE_LOCATION', 'eastus'),
            containers=[container],
            os_type=OperatingSystemTypes.linux,
            restart_policy=ContainerGroupRestartPolicy.never,
            image_registry_credentials=registry_credentials,
            tags={
                'genx-case': case_name,
                'triggered-by': 'event-grid',
                'created-at': time.strftime('%Y-%m-%d_%H-%M-%S')
            }
        )
        
        # Create the container group
        logging.info(f'Creating container group: {container_name}')
        poller = aci_client.container_groups.begin_create_or_update(
            resource_group_name=resource_group,
            container_group_name=container_name,
            container_group=container_group
        )
        
        # Wait for creation to complete
        result = poller.result()
        logging.info(f'Container group created: {result.name}')
        return True
        
    except Exception as e:
        logging.error(f'Error creating container: {str(e)}')
        return False


@app.route(route="status", auth_level=func.AuthLevel.FUNCTION)
def status(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to check the status of GenX processing jobs.
    """
    logging.info('Status endpoint called')
    
    try:
        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        resource_group = os.environ.get('AZURE_RESOURCE_GROUP', 'genx-rg')
        
        credential = DefaultAzureCredential()
        aci_client = ContainerInstanceManagementClient(credential, subscription_id)
        
        # Get all container groups with GenX tags
        container_groups = aci_client.container_groups.list_by_resource_group(resource_group)
        genx_containers = []
        
        for container_group in container_groups:
            if container_group.tags and 'genx-case' in container_group.tags:
                genx_containers.append({
                    'name': container_group.name,
                    'case': container_group.tags.get('genx-case'),
                    'status': container_group.instance_view.state if container_group.instance_view else 'Unknown',
                    'created': container_group.tags.get('created-at'),
                    'location': container_group.location
                })
        
        return func.HttpResponse(
            json.dumps({
                'active_jobs': len(genx_containers),
                'containers': genx_containers
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f'Error getting status: {str(e)}')
        return func.HttpResponse(
            json.dumps({'error': str(e)}),
            status_code=500,
            mimetype="application/json"
        )
