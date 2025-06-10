#!/usr/bin/env python3
"""
Production monitoring and management script for GenX Azure infrastructure.
This script provides comprehensive monitoring and management capabilities.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.storage.blob import BlobServiceClient
import requests

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

class GenXMonitor:
    def __init__(self, resource_group, subscription_id=None):
        self.resource_group = resource_group
        self.subscription_id = subscription_id or self._get_subscription_id()
        self.credential = DefaultAzureCredential()
        
        # Initialize Azure clients
        self.aci_client = ContainerInstanceManagementClient(self.credential, self.subscription_id)
        self.monitor_client = MonitorManagementClient(self.credential, self.subscription_id)
        self.storage_client = StorageManagementClient(self.credential, self.subscription_id)
        self.web_client = WebSiteManagementClient(self.credential, self.subscription_id)

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
            print(f"{Colors.RED}Failed to get Azure subscription ID{Colors.NC}")
            sys.exit(1)

    def log(self, message, color=Colors.BLUE):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{color}[{timestamp}]{Colors.NC} {message}")

    def list_active_containers(self):
        """List all active GenX containers"""
        self.log("📦 Active GenX Containers", Colors.CYAN)
        print("-" * 80)
        
        try:
            containers = list(self.aci_client.container_groups.list_by_resource_group(self.resource_group))
            genx_containers = [c for c in containers if 'genx' in c.name.lower()]
            
            if not genx_containers:
                print(f"{Colors.YELLOW}No active GenX containers found{Colors.NC}")
                return []
            
            print(f"{'Name':<30} {'Status':<15} {'Created':<20} {'Case':<20}")
            print("-" * 80)
            
            for container in genx_containers:
                name = container.name
                status = container.instance_view.state if container.instance_view else 'Unknown'
                created = container.tags.get('created-at', 'Unknown') if container.tags else 'Unknown'
                case = container.tags.get('genx-case', 'Unknown') if container.tags else 'Unknown'
                
                # Color code status
                if status == 'Running':
                    status_colored = f"{Colors.GREEN}{status}{Colors.NC}"
                elif status in ['Succeeded', 'Terminated']:
                    status_colored = f"{Colors.BLUE}{status}{Colors.NC}"
                elif status in ['Failed', 'Pending']:
                    status_colored = f"{Colors.RED}{status}{Colors.NC}"
                else:
                    status_colored = f"{Colors.YELLOW}{status}{Colors.NC}"
                
                print(f"{name:<30} {status_colored:<24} {created:<20} {case:<20}")
            
            return genx_containers
            
        except Exception as e:
            print(f"{Colors.RED}Error listing containers: {str(e)}{Colors.NC}")
            return []

    def get_container_logs(self, container_name):
        """Get logs for a specific container"""
        self.log(f"📋 Logs for container: {container_name}", Colors.PURPLE)
        
        try:
            logs = self.aci_client.container_logs.list(
                self.resource_group, container_name, container_name
            )
            
            if logs.content:
                print("-" * 80)
                print(logs.content)
                print("-" * 80)
            else:
                print(f"{Colors.YELLOW}No logs available for container{Colors.NC}")
                
        except Exception as e:
            print(f"{Colors.RED}Error getting logs: {str(e)}{Colors.NC}")

    def cleanup_completed_containers(self, max_age_hours=24):
        """Clean up completed containers older than specified hours"""
        self.log(f"🧹 Cleaning up containers older than {max_age_hours} hours", Colors.YELLOW)
        
        try:
            containers = list(self.aci_client.container_groups.list_by_resource_group(self.resource_group))
            genx_containers = [c for c in containers if 'genx' in c.name.lower()]
            
            cleaned_count = 0
            for container in genx_containers:
                # Check if container is completed
                if container.instance_view and container.instance_view.state in ['Succeeded', 'Failed', 'Terminated']:
                    # Check age
                    if container.tags and 'created-at' in container.tags:
                        try:
                            created_time = datetime.fromisoformat(container.tags['created-at'].replace('_', ' '))
                            age = datetime.now() - created_time
                            
                            if age.total_seconds() > max_age_hours * 3600:
                                print(f"Deleting container: {container.name} (age: {age})")
                                self.aci_client.container_groups.begin_delete(
                                    self.resource_group, container.name
                                )
                                cleaned_count += 1
                        except Exception as e:
                            print(f"Warning: Could not parse creation time for {container.name}: {e}")
            
            print(f"{Colors.GREEN}Cleaned up {cleaned_count} containers{Colors.NC}")
            
        except Exception as e:
            print(f"{Colors.RED}Error during cleanup: {str(e)}{Colors.NC}")

    def monitor_storage_usage(self, storage_account):
        """Monitor storage account usage"""
        self.log(f"💾 Storage Usage for {storage_account}", Colors.CYAN)
        
        try:
            # Get storage account metrics
            storage_resource_id = f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/providers/Microsoft.Storage/storageAccounts/{storage_account}"
            
            # Get usage metrics for the last 24 hours
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)
            
            metrics = self.monitor_client.metrics.list(
                resource_uri=storage_resource_id,
                timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                interval='PT1H',
                metricnames='UsedCapacity,BlobCount,ContainerCount'
            )
            
            print("-" * 50)
            for metric in metrics.value:
                print(f"Metric: {metric.name.value}")
                if metric.timeseries:
                    latest_data = metric.timeseries[0].data[-1] if metric.timeseries[0].data else None
                    if latest_data and latest_data.total:
                        value = latest_data.total
                        unit = metric.unit.value if metric.unit else 'units'
                        print(f"  Latest Value: {value:,.0f} {unit}")
                print()
            
        except Exception as e:
            print(f"{Colors.RED}Error getting storage metrics: {str(e)}{Colors.NC}")

    def check_function_health(self, function_app):
        """Check Function App health and recent executions"""
        self.log(f"⚡ Function App Health: {function_app}", Colors.GREEN)
        
        try:
            # Get function app info
            app = self.web_client.web_apps.get(self.resource_group, function_app)
            
            print(f"Status: {Colors.GREEN if app.state == 'Running' else Colors.YELLOW}{app.state}{Colors.NC}")
            print(f"Location: {app.location}")
            print(f"Runtime: {app.site_config.linux_fx_version if app.site_config else 'Unknown'}")
            
            # Try to get function execution count
            try:
                function_url = f"https://{function_app}.azurewebsites.net/api/status"
                response = requests.get(function_url, timeout=10)
                print(f"Endpoint Status: {Colors.GREEN}Accessible{Colors.NC}")
            except requests.RequestException:
                print(f"Endpoint Status: {Colors.YELLOW}Not accessible (may require authentication){Colors.NC}")
            
        except Exception as e:
            print(f"{Colors.RED}Error checking function health: {str(e)}{Colors.NC}")

    def list_recent_cases(self, storage_account, storage_key, days=7):
        """List recently processed cases"""
        self.log(f"📊 Recent Cases (last {days} days)", Colors.BLUE)
        
        try:
            blob_service_client = BlobServiceClient(
                account_url=f"https://{storage_account}.blob.core.windows.net",
                credential=storage_key
            )
            
            # List cases container
            cases_container = blob_service_client.get_container_client("cases")
            results_container = blob_service_client.get_container_client("results")
            
            # Get case folders from last week
            cutoff_date = datetime.now() - timedelta(days=days)
            
            cases = set()
            for blob in cases_container.list_blobs():
                if blob.creation_time and blob.creation_time.replace(tzinfo=None) > cutoff_date:
                    case_name = blob.name.split('/')[0]
                    cases.add(case_name)
            
            print(f"{'Case Name':<30} {'Status':<15} {'Files':<10}")
            print("-" * 60)
            
            for case in sorted(cases):
                # Check if results exist
                results_exist = False
                file_count = 0
                try:
                    result_blobs = list(results_container.list_blobs(name_starts_with=f"{case}/"))
                    results_exist = len(result_blobs) > 0
                    file_count = len(result_blobs)
                except:
                    pass
                
                status = f"{Colors.GREEN}Completed{Colors.NC}" if results_exist else f"{Colors.YELLOW}Processing{Colors.NC}"
                print(f"{case:<30} {status:<24} {file_count:<10}")
                
        except Exception as e:
            print(f"{Colors.RED}Error listing recent cases: {str(e)}{Colors.NC}")

    def generate_report(self, storage_account, function_app, output_file=None):
        """Generate a comprehensive status report"""
        self.log("📊 Generating Status Report", Colors.PURPLE)
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"GenX Azure Infrastructure Status Report")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Resource Group: {self.resource_group}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Container summary
        containers = list(self.aci_client.container_groups.list_by_resource_group(self.resource_group))
        genx_containers = [c for c in containers if 'genx' in c.name.lower()]
        
        running_count = sum(1 for c in genx_containers if c.instance_view and c.instance_view.state == 'Running')
        completed_count = sum(1 for c in genx_containers if c.instance_view and c.instance_view.state in ['Succeeded', 'Terminated'])
        failed_count = sum(1 for c in genx_containers if c.instance_view and c.instance_view.state == 'Failed')
        
        report_lines.append("CONTAINER SUMMARY:")
        report_lines.append(f"  Total Containers: {len(genx_containers)}")
        report_lines.append(f"  Running: {running_count}")
        report_lines.append(f"  Completed: {completed_count}")
        report_lines.append(f"  Failed: {failed_count}")
        report_lines.append("")
        
        # Function app status
        try:
            app = self.web_client.web_apps.get(self.resource_group, function_app)
            report_lines.append("FUNCTION APP STATUS:")
            report_lines.append(f"  Name: {function_app}")
            report_lines.append(f"  Status: {app.state}")
            report_lines.append(f"  Location: {app.location}")
            report_lines.append("")
        except Exception as e:
            report_lines.append(f"FUNCTION APP STATUS: Error - {str(e)}")
            report_lines.append("")
        
        report_lines.append("=" * 80)
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            print(f"{Colors.GREEN}Report saved to: {output_file}{Colors.NC}")
        else:
            print(report_content)

def main():
    parser = argparse.ArgumentParser(description="Monitor and manage GenX Azure infrastructure")
    parser.add_argument("--resource-group", required=True, help="Azure resource group name")
    parser.add_argument("--storage-account", help="Storage account name")
    parser.add_argument("--function-app", help="Function app name")
    parser.add_argument("--storage-key", help="Storage account key")
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List containers command
    list_cmd = subparsers.add_parser('list', help='List active containers')
    
    # Logs command
    logs_cmd = subparsers.add_parser('logs', help='Get container logs')
    logs_cmd.add_argument('container_name', help='Container name')
    
    # Cleanup command
    cleanup_cmd = subparsers.add_parser('cleanup', help='Clean up old containers')
    cleanup_cmd.add_argument('--max-age-hours', type=int, default=24, help='Maximum age in hours')
    
    # Monitor command
    monitor_cmd = subparsers.add_parser('monitor', help='Monitor system status')
    
    # Report command
    report_cmd = subparsers.add_parser('report', help='Generate status report')
    report_cmd.add_argument('--output', help='Output file for report')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    monitor = GenXMonitor(args.resource_group)
    
    try:
        if args.command == 'list':
            monitor.list_active_containers()
            
        elif args.command == 'logs':
            monitor.get_container_logs(args.container_name)
            
        elif args.command == 'cleanup':
            monitor.cleanup_completed_containers(args.max_age_hours)
            
        elif args.command == 'monitor':
            monitor.list_active_containers()
            print()
            if args.storage_account:
                monitor.monitor_storage_usage(args.storage_account)
                print()
            if args.function_app:
                monitor.check_function_health(args.function_app)
                print()
            if args.storage_account and args.storage_key:
                monitor.list_recent_cases(args.storage_account, args.storage_key)
                
        elif args.command == 'report':
            if not args.function_app:
                print(f"{Colors.YELLOW}Warning: --function-app not provided, function status will be skipped{Colors.NC}")
            monitor.generate_report(args.storage_account, args.function_app, args.output)
        
        return 0
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Operation cancelled by user{Colors.NC}")
        return 1
    except Exception as e:
        print(f"{Colors.RED}Error: {str(e)}{Colors.NC}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
