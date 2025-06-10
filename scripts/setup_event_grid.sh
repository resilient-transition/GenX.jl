#!/bin/bash

# Azure Event Grid Setup Script for GenX Automation
# This script sets up Event Grid to monitor blob storage uploads and trigger GenX processing

set -e

# Configuration
RESOURCE_GROUP="genx-rg"
LOCATION="eastus"
STORAGE_ACCOUNT="genxstorage"
FUNCTION_APP_NAME="genx-eventgrid-function"
EVENT_SUBSCRIPTION_NAME="genx-blob-trigger"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if logged in to Azure
echo_info "Checking Azure login status..."
if ! az account show &> /dev/null; then
    echo_error "Please login to Azure using 'az login'"
    exit 1
fi

# Get subscription info
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
echo_info "Using subscription: $SUBSCRIPTION_ID"

# Create resource group if it doesn't exist
echo_info "Ensuring resource group exists: $RESOURCE_GROUP"
az group create --name $RESOURCE_GROUP --location $LOCATION --output none
echo_success "Resource group ready"

# Create storage account if it doesn't exist
echo_info "Ensuring storage account exists: $STORAGE_ACCOUNT"
if ! az storage account show --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo_info "Creating storage account..."
    az storage account create \
        --name $STORAGE_ACCOUNT \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku Standard_LRS \
        --kind StorageV2 \
        --access-tier Hot \
        --output none
    echo_success "Storage account created"
else
    echo_success "Storage account already exists"
fi

# Get storage account key
STORAGE_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT --query '[0].value' --output tsv)

# Create containers if they don't exist
echo_info "Ensuring storage containers exist..."
az storage container create --name "cases" --account-name $STORAGE_ACCOUNT --account-key "$STORAGE_KEY" --output none
az storage container create --name "results" --account-name $STORAGE_ACCOUNT --account-key "$STORAGE_KEY" --output none
echo_success "Storage containers ready"

# Create App Service Plan for Functions
echo_info "Ensuring App Service Plan exists..."
PLAN_NAME="genx-function-plan"
if ! az appservice plan show --name $PLAN_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo_info "Creating App Service Plan..."
    az appservice plan create \
        --name $PLAN_NAME \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --sku B1 \
        --is-linux \
        --output none
    echo_success "App Service Plan created"
else
    echo_success "App Service Plan already exists"
fi

# Create Function App
echo_info "Ensuring Function App exists: $FUNCTION_APP_NAME"
if ! az functionapp show --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo_info "Creating Function App..."
    az functionapp create \
        --name $FUNCTION_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --plan $PLAN_NAME \
        --runtime python \
        --runtime-version 3.11 \
        --storage-account $STORAGE_ACCOUNT \
        --os-type Linux \
        --output none
    echo_success "Function App created"
else
    echo_success "Function App already exists"
fi

# Configure Function App settings
echo_info "Configuring Function App settings..."
az functionapp config appsettings set \
    --name $FUNCTION_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --settings \
        "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID" \
        "AZURE_RESOURCE_GROUP=$RESOURCE_GROUP" \
        "AZURE_STORAGE_ACCOUNT=$STORAGE_ACCOUNT" \
        "AZURE_STORAGE_KEY=$STORAGE_KEY" \
        "AZURE_LOCATION=$LOCATION" \
        "AZURE_REGISTRY_NAME=genxjlregistry" \
    --output none
echo_success "Function App settings configured"

# Enable system-assigned managed identity
echo_info "Enabling managed identity for Function App..."
az functionapp identity assign --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP --output none
echo_success "Managed identity enabled"

# Get Function App's managed identity
FUNCTION_PRINCIPAL_ID=$(az functionapp identity show --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP --query principalId --output tsv)

# Assign roles to the managed identity
echo_info "Assigning roles to Function App managed identity..."

# Container Instance Contributor role
az role assignment create \
    --assignee $FUNCTION_PRINCIPAL_ID \
    --role "Contributor" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
    --output none

# Storage Blob Data Contributor role
STORAGE_SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"
az role assignment create \
    --assignee $FUNCTION_PRINCIPAL_ID \
    --role "Storage Blob Data Contributor" \
    --scope $STORAGE_SCOPE \
    --output none

echo_success "Roles assigned to managed identity"

# Create Event Grid topic if it doesn't exist
TOPIC_NAME="genx-blob-events"
echo_info "Ensuring Event Grid topic exists: $TOPIC_NAME"
if ! az eventgrid topic show --name $TOPIC_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo_info "Creating Event Grid topic..."
    az eventgrid topic create \
        --name $TOPIC_NAME \
        --resource-group $RESOURCE_GROUP \
        --location $LOCATION \
        --output none
    echo_success "Event Grid topic created"
else
    echo_success "Event Grid topic already exists"
fi

# Get Function App URL for webhook
FUNCTION_URL="https://${FUNCTION_APP_NAME}.azurewebsites.net/api/blob_trigger"

# Create Event Grid subscription for blob storage
echo_info "Creating Event Grid subscription..."
STORAGE_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"

# Remove existing subscription if it exists
if az eventgrid event-subscription show --name $EVENT_SUBSCRIPTION_NAME --source-resource-id $STORAGE_RESOURCE_ID &> /dev/null; then
    echo_info "Removing existing Event Grid subscription..."
    az eventgrid event-subscription delete \
        --name $EVENT_SUBSCRIPTION_NAME \
        --source-resource-id $STORAGE_RESOURCE_ID \
        --output none
fi

# Create new subscription
az eventgrid event-subscription create \
    --name $EVENT_SUBSCRIPTION_NAME \
    --source-resource-id $STORAGE_RESOURCE_ID \
    --endpoint $FUNCTION_URL \
    --endpoint-type webhook \
    --included-event-types Microsoft.Storage.BlobCreated \
    --subject-begins-with "/blobServices/default/containers/cases/" \
    --output none

echo_success "Event Grid subscription created"

# Deploy Function App code
echo_info "Function App deployment information:"
echo "  Function App Name: $FUNCTION_APP_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Function URL: $FUNCTION_URL"
echo ""
echo "To deploy your function code, run:"
echo "  cd azure-function"
echo "  func azure functionapp publish $FUNCTION_APP_NAME"
echo ""

# Show summary
echo_success "Azure Event Grid setup completed!"
echo ""
echo "📋 Setup Summary:"
echo "├── Resource Group: $RESOURCE_GROUP"
echo "├── Storage Account: $STORAGE_ACCOUNT"
echo "├── Function App: $FUNCTION_APP_NAME"
echo "├── Event Grid Topic: $TOPIC_NAME"
echo "├── Event Subscription: $EVENT_SUBSCRIPTION_NAME"
echo "└── Containers: cases, results"
echo ""
echo "🔗 Important URLs:"
echo "├── Function App: https://${FUNCTION_APP_NAME}.azurewebsites.net"
echo "├── Status Endpoint: https://${FUNCTION_APP_NAME}.azurewebsites.net/api/status"
echo "└── Storage Account: https://${STORAGE_ACCOUNT}.blob.core.windows.net"
echo ""
echo "📁 Next Steps:"
echo "1. Deploy the function code: func azure functionapp publish $FUNCTION_APP_NAME"
echo "2. Upload a test case to the 'cases' container"
echo "3. Monitor the Function App logs for processing"
echo "4. Check the 'results' container for outputs"
echo ""
echo_success "Setup complete! 🎉"
