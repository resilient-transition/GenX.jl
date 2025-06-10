#!/usr/bin/env python3
"""
Deployment validation script for GenX Azure infrastructure.
This script validates that all components are properly deployed and functional.
"""

import os
import sys
import json
import time
import requests
import argparse
from pathlib import Path
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def log(message, color=Colors.BLUE):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{color}[{timestamp}]{Colors.NC} {message}")

def success(message):
    print(f"{Colors.GREEN}✓{Colors.NC} {message}")

def warning(message):
    print(f"{Colors.YELLOW}⚠{Colors.NC} {message}")

def error(message):
    print(f"{Colors.RED}✗{Colors.NC} {message}")

class AzureValidator:
    def __init__(self, resource_group, subscription_id=None):
        self.resource_group = resource_group
        self.subscription_id = subscription_id or self._get_subscription_id()
        self.credential = DefaultAzureCredential()
        
    def _get_subscription_id(self):
        """Get the current Azure subscription ID"""
        import subprocess
        try:
            result = subprocess.run(
                ['az', 'account', 'show', '--query', 'id', '--output', 'tsv'],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            error("Failed to get Azure subscription ID. Please ensure Azure CLI is logged in.")
            sys.exit(1)

    def validate_resource_group(self):
        """Validate resource group exists"""
        log("Validating resource group...")
        try:
            import subprocess
            result = subprocess.run(
                ['az', 'group', 'exists', '--name', self.resource_group],
                capture_output=True, text=True, check=True
            )
            if result.stdout.strip().lower() == 'true':
                success(f"Resource group '{self.resource_group}' exists")
                return True
            else:
                error(f"Resource group '{self.resource_group}' does not exist")
                return False
        except Exception as e:
            error(f"Failed to validate resource group: {str(e)}")
            return False

    def validate_storage_account(self, storage_account):
        """Validate storage account and containers"""
        log("Validating storage account...")
        try:
            storage_client = StorageManagementClient(self.credential, self.subscription_id)
            
            # Check if storage account exists
            storage_account_obj = storage_client.storage_accounts.get_properties(
                self.resource_group, storage_account
            )
            success(f"Storage account '{storage_account}' exists")
            
            # Validate containers
            blob_service_client = BlobServiceClient(
                account_url=f"https://{storage_account}.blob.core.windows.net",
                credential=self.credential
            )
            
            required_containers = ['cases', 'results', 'logs']
            for container in required_containers:
                try:
                    container_client = blob_service_client.get_container_client(container)
                    container_client.get_container_properties()
                    success(f"Container '{container}' exists")
                except Exception:
                    error(f"Container '{container}' does not exist")
                    return False
            
            return True
        except Exception as e:
            error(f"Failed to validate storage account: {str(e)}")
            return False

    def validate_container_registry(self, registry_name):
        """Validate container registry"""
        log("Validating container registry...")
        try:
            import subprocess
            result = subprocess.run(
                ['az', 'acr', 'show', '--name', registry_name, '--resource-group', self.resource_group],
                capture_output=True, text=True, check=True
            )
            registry_info = json.loads(result.stdout)
            success(f"Container registry '{registry_name}' exists")
            
            # Check for GenX image
            try:
                result = subprocess.run(
                    ['az', 'acr', 'repository', 'show', '--name', registry_name, '--image', 'genx-jl:latest'],
                    capture_output=True, text=True, check=True
                )
                success("GenX container image exists in registry")
            except subprocess.CalledProcessError:
                warning("GenX container image not found in registry")
            
            return True
        except Exception as e:
            error(f"Failed to validate container registry: {str(e)}")
            return False

    def validate_function_app(self, function_app):
        """Validate Azure Function App"""
        log("Validating Function App...")
        try:
            web_client = WebSiteManagementClient(self.credential, self.subscription_id)
            
            # Check if function app exists
            app = web_client.web_apps.get(self.resource_group, function_app)
            success(f"Function App '{function_app}' exists")
            
            # Check function app status
            if app.state == 'Running':
                success("Function App is running")
            else:
                warning(f"Function App state: {app.state}")
            
            # Test function endpoint
            try:
                function_url = f"https://{function_app}.azurewebsites.net/api/status"
                response = requests.get(function_url, timeout=30)
                if response.status_code == 200 or response.status_code == 401:  # 401 is expected without auth
                    success("Function App endpoint is accessible")
                else:
                    warning(f"Function App endpoint returned status: {response.status_code}")
            except requests.RequestException as e:
                warning(f"Could not reach function endpoint: {str(e)}")
            
            return True
        except Exception as e:
            error(f"Failed to validate Function App: {str(e)}")
            return False

    def validate_event_grid(self, storage_account):
        """Validate Event Grid subscription"""
        log("Validating Event Grid subscription...")
        try:
            import subprocess
            
            # Get storage account resource ID
            result = subprocess.run([
                'az', 'storage', 'account', 'show',
                '--name', storage_account,
                '--resource-group', self.resource_group,
                '--query', 'id',
                '--output', 'tsv'
            ], capture_output=True, text=True, check=True)
            
            storage_resource_id = result.stdout.strip()
            
            # List event subscriptions for the storage account
            result = subprocess.run([
                'az', 'eventgrid', 'event-subscription', 'list',
                '--source-resource-id', storage_resource_id
            ], capture_output=True, text=True, check=True)
            
            subscriptions = json.loads(result.stdout)
            if subscriptions:
                success(f"Found {len(subscriptions)} Event Grid subscription(s)")
                return True
            else:
                error("No Event Grid subscriptions found")
                return False
                
        except Exception as e:
            error(f"Failed to validate Event Grid: {str(e)}")
            return False

    def test_end_to_end_workflow(self, storage_account, storage_key):
        """Test the complete workflow with a sample case"""
        log("Testing end-to-end workflow...")
        
        try:
            # Create test case data
            test_case_name = f"validation-test-{int(time.time())}"
            test_data = "# GenX validation test case\ntest_parameter = 1\n"
            
            # Upload test file
            blob_service_client = BlobServiceClient(
                account_url=f"https://{storage_account}.blob.core.windows.net",
                credential=storage_key
            )
            
            blob_client = blob_service_client.get_blob_client(
                container="cases", 
                blob=f"{test_case_name}/test_file.txt"
            )
            
            blob_client.upload_blob(test_data, overwrite=True)
            success("Test case uploaded successfully")
            
            # Wait a moment for Event Grid processing
            log("Waiting for Event Grid processing...")
            time.sleep(30)
            
            # Check if container was created
            aci_client = ContainerInstanceManagementClient(self.credential, self.subscription_id)
            containers = list(aci_client.container_groups.list_by_resource_group(self.resource_group))
            
            test_containers = [c for c in containers if test_case_name in c.name]
            if test_containers:
                success("Container instance was created for test case")
                return True
            else:
                warning("No container instance found for test case (may take longer to process)")
                return False
                
        except Exception as e:
            error(f"End-to-end test failed: {str(e)}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Validate GenX Azure deployment")
    parser.add_argument("--resource-group", required=True, help="Azure resource group name")
    parser.add_argument("--storage-account", required=True, help="Storage account name")
    parser.add_argument("--registry", required=True, help="Container registry name")
    parser.add_argument("--function-app", required=True, help="Function app name")
    parser.add_argument("--storage-key", help="Storage account key for testing")
    parser.add_argument("--skip-e2e", action="store_true", help="Skip end-to-end testing")
    
    args = parser.parse_args()
    
    print(f"{Colors.BLUE}")
    print("=" * 50)
    print("GenX Azure Deployment Validation")
    print("=" * 50)
    print(f"{Colors.NC}")
    
    validator = AzureValidator(args.resource_group)
    
    tests = [
        ("Resource Group", lambda: validator.validate_resource_group()),
        ("Storage Account", lambda: validator.validate_storage_account(args.storage_account)),
        ("Container Registry", lambda: validator.validate_container_registry(args.registry)),
        ("Function App", lambda: validator.validate_function_app(args.function_app)),
        ("Event Grid", lambda: validator.validate_event_grid(args.storage_account)),
    ]
    
    # Run validation tests
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            error(f"Test '{test_name}' failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Run end-to-end test if requested and storage key provided
    if not args.skip_e2e and args.storage_key:
        try:
            e2e_result = validator.test_end_to_end_workflow(args.storage_account, args.storage_key)
            results.append(("End-to-End Workflow", e2e_result))
        except Exception as e:
            error(f"End-to-end test failed: {str(e)}")
            results.append(("End-to-End Workflow", False))
    elif not args.skip_e2e:
        warning("Skipping end-to-end test: --storage-key not provided")
    
    # Print summary
    print(f"\n{Colors.BLUE}Validation Summary:{Colors.NC}")
    print("-" * 30)
    
    passed_tests = 0
    total_tests = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status:>6}{Colors.NC} {test_name}")
        if result:
            passed_tests += 1
    
    print("-" * 30)
    print(f"Passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print(f"\n{Colors.GREEN}🎉 All validation tests passed!{Colors.NC}")
        print("Your GenX Azure deployment is ready for production use.")
        return 0
    else:
        print(f"\n{Colors.RED}❌ Some validation tests failed.{Colors.NC}")
        print("Please review the errors above and fix the issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
