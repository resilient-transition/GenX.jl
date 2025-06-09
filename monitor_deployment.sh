#!/bin/bash

# Azure Container Apps Workflow Monitor
# This script monitors the GenX workflow execution and Azure resources

WORKFLOW_ID="15542956855"
RESOURCE_GROUP="genx-rg"

echo "🔍 Monitoring GenX Azure Container Apps Deployment"
echo "Workflow ID: $WORKFLOW_ID"
echo "Resource Group: $RESOURCE_GROUP"
echo "============================================="

# Function to check workflow status
check_workflow() {
    echo -n "📊 Workflow Status: "
    gh run view $WORKFLOW_ID --json status,conclusion | jq -r '.status + " (" + (.conclusion // "running") + ")"'
}

# Function to check workflow jobs
check_jobs() {
    echo "🔧 Job Details:"
    gh run view $WORKFLOW_ID --json jobs | jq -r '.jobs[] | "  " + .name + ": " + .status + " (" + (.conclusion // "running") + ")"'
}

# Function to check Azure resources
check_azure_resources() {
    echo "☁️  Azure Resources:"
    
    # Container Registries
    echo -n "  📦 Container Registries: "
    az acr list --resource-group $RESOURCE_GROUP --query "length([*])" -o tsv 2>/dev/null || echo "0"
    
    # Container App Environments
    echo -n "  🏢 Container App Environments: "
    az containerapp env list --resource-group $RESOURCE_GROUP --query "length([*])" -o tsv 2>/dev/null || echo "0"
    
    # Container Apps/Jobs
    echo -n "  🚀 Container Apps: "
    az containerapp list --resource-group $RESOURCE_GROUP --query "length([*])" -o tsv 2>/dev/null || echo "0"
    
    echo -n "  ⚙️  Container Jobs: "
    az containerapp job list --resource-group $RESOURCE_GROUP --query "length([*])" -o tsv 2>/dev/null || echo "0"
}

# Function to check blob storage
check_blob_storage() {
    echo "📁 Blob Storage Status:"
    echo -n "  📤 Input files: "
    az storage blob list --container-name genx-data --account-name genxstor1749495194 --prefix "1_three_zones" --query "length([*])" -o tsv 2>/dev/null || echo "0"
    
    echo -n "  📥 Output files: "
    az storage blob list --container-name genx-data --account-name genxstor1749495194 --prefix "outputs" --query "length([*])" -o tsv 2>/dev/null || echo "0"
}

# Main monitoring loop
monitor_continuously() {
    while true; do
        clear
        echo "🔍 GenX Azure Container Apps Monitor - $(date)"
        echo "============================================="
        
        check_workflow
        echo
        check_jobs
        echo
        check_azure_resources
        echo
        check_blob_storage
        echo
        
        # Check if workflow is complete
        STATUS=$(gh run view $WORKFLOW_ID --json status | jq -r '.status')
        if [[ "$STATUS" == "completed" ]]; then
            echo "✅ Workflow completed!"
            CONCLUSION=$(gh run view $WORKFLOW_ID --json conclusion | jq -r '.conclusion')
            echo "Final result: $CONCLUSION"
            break
        fi
        
        echo "⏱️  Refreshing in 30 seconds... (Ctrl+C to stop)"
        sleep 30
    done
}

# Check if we want continuous monitoring or one-time check
if [[ "$1" == "--continuous" ]]; then
    monitor_continuously
else
    check_workflow
    echo
    check_jobs
    echo
    check_azure_resources
    echo
    check_blob_storage
    echo
    echo "Run with --continuous for real-time monitoring"
fi
