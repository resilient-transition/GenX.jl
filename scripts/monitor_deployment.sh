#!/bin/bash

# GenX Event Grid Monitoring and Management Script
# This script helps monitor and manage the GenX Event Grid workflow

set -e

# Configuration
RESOURCE_GROUP="genx-rg"
STORAGE_ACCOUNT="genxdata"
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

show_help() {
    echo "GenX Event Grid Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  status      Show status of all components"
    echo "  logs        Show Function App logs (real-time)"
    echo "  test        Upload a test case to trigger processing"
    echo "  containers  List active container instances"
    echo "  clean       Clean up completed container instances"
    echo "  deploy      Deploy function code"
    echo "  results     List results in blob storage"
    echo "  help        Show this help message"
    echo ""
}

show_status() {
    echo_info "Checking GenX Event Grid system status..."
    echo ""
    
    # Check Resource Group
    echo "📦 Resource Group: $RESOURCE_GROUP"
    if az group show --name $RESOURCE_GROUP &> /dev/null; then
        echo_success "  ✅ Exists"
    else
        echo_error "  ❌ Not found"
        return 1
    fi
    
    # Check Storage Account
    echo "💾 Storage Account: $STORAGE_ACCOUNT"
    if az storage account show --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP &> /dev/null; then
        echo_success "  ✅ Exists"
        
        # Check containers
        STORAGE_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT --query '[0].value' --output tsv)
        
        echo "  📁 Containers:"
        if az storage container show --name "cases" --account-name $STORAGE_ACCOUNT --account-key "$STORAGE_KEY" &> /dev/null; then
            CASES_COUNT=$(az storage blob list --container-name "cases" --account-name $STORAGE_ACCOUNT --account-key "$STORAGE_KEY" --query 'length(@)' --output tsv)
            echo_success "    ✅ cases ($CASES_COUNT files)"
        else
            echo_error "    ❌ cases container missing"
        fi
        
        if az storage container show --name "results" --account-name $STORAGE_ACCOUNT --account-key "$STORAGE_KEY" &> /dev/null; then
            RESULTS_COUNT=$(az storage blob list --container-name "results" --account-name $STORAGE_ACCOUNT --account-key "$STORAGE_KEY" --query 'length(@)' --output tsv)
            echo_success "    ✅ results ($RESULTS_COUNT files)"
        else
            echo_error "    ❌ results container missing"
        fi
    else
        echo_error "  ❌ Not found"
    fi
    
    # Check Function App
    echo "⚡ Function App: $FUNCTION_APP_NAME"
    if az functionapp show --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP &> /dev/null; then
        STATE=$(az functionapp show --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP --query state --output tsv)
        if [ "$STATE" = "Running" ]; then
            echo_success "  ✅ Running"
        else
            echo_warning "  ⚠️ State: $STATE"
        fi
        
        # Check function endpoint
        FUNCTION_URL="https://${FUNCTION_APP_NAME}.azurewebsites.net/api/status"
        echo "  🔗 Status endpoint: $FUNCTION_URL"
    else
        echo_error "  ❌ Not found"
    fi
    
    # Check Event Grid subscription
    echo "📡 Event Grid Subscription: $EVENT_SUBSCRIPTION_NAME"
    STORAGE_RESOURCE_ID="/subscriptions/$(az account show --query id --output tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"
    if az eventgrid event-subscription show --name $EVENT_SUBSCRIPTION_NAME --source-resource-id $STORAGE_RESOURCE_ID &> /dev/null; then
        echo_success "  ✅ Active"
    else
        echo_error "  ❌ Not found"
    fi
    
    echo ""
    echo_success "Status check complete"
}

show_logs() {
    echo_info "Streaming Function App logs (Press Ctrl+C to stop)..."
    az functionapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP
}

test_upload() {
    echo_info "Testing Event Grid trigger with sample case..."
    
    # Get storage key
    STORAGE_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT --query '[0].value' --output tsv)
    
    # Create a test case
    TEST_CASE="test_case_$(date +%Y%m%d_%H%M%S)"
    TEST_DIR="/tmp/$TEST_CASE"
    mkdir -p "$TEST_DIR"
    
    # Create minimal test files
    cat > "$TEST_DIR/genx_settings.yml" << EOF
NetworkExpansion: 0
Trans_Loss_Segments: 1
Reserves: 0
EnergyShareRequirement: 0
CapacityReserveMargin: 0
CO2Cap: 0
EOF
    
    cat > "$TEST_DIR/Load_data.csv" << EOF
Time_Index,Load_MW_z1,Load_MW_z2,Load_MW_z3
1,1000,800,600
2,1100,850,650
3,1050,825,625
4,1000,800,600
EOF
    
    cat > "$TEST_DIR/Generators_data.csv" << EOF
Resource,Zone,Fuel,Var_OM_Cost_per_MWh,Start_Cost_per_MW,Cap_Size,Existing_Cap_MW
Gas_1,1,Natural_Gas,50,100,100,500
Gas_2,2,Natural_Gas,55,100,100,400
Gas_3,3,Natural_Gas,60,100,100,300
EOF
    
    cat > "$TEST_DIR/Fuels_data.csv" << EOF
Fuel,CO2_Content_Tons_per_MMBtu,Fuel_Price_per_MMBtu
Natural_Gas,0.0531,4.0
EOF
    
    echo_info "Uploading test case: $TEST_CASE"
    
    # Upload test files
    az storage blob upload-batch \
        --destination "cases/$TEST_CASE" \
        --source "$TEST_DIR" \
        --account-name $STORAGE_ACCOUNT \
        --account-key "$STORAGE_KEY" \
        --output none
    
    echo_success "Test case uploaded: $TEST_CASE"
    echo_info "Monitor the Function App logs to see processing:"
    echo "  $0 logs"
    echo ""
    echo_info "Check results after processing:"
    echo "  $0 results"
    
    # Cleanup
    rm -rf "$TEST_DIR"
}

list_containers() {
    echo_info "Listing active GenX container instances..."
    
    CONTAINERS=$(az container list --resource-group $RESOURCE_GROUP --query "[?tags.\"genx-case\"]" --output json)
    
    if [ "$CONTAINERS" = "[]" ]; then
        echo_info "No active GenX containers found"
        return
    fi
    
    echo "$CONTAINERS" | jq -r '.[] | "🐳 \(.name) - Case: \(.tags."genx-case") - State: \(.instanceView.state) - Created: \(.tags."created-at" // "unknown")"'
}

clean_containers() {
    echo_info "Cleaning up completed container instances..."
    
    # Get completed containers
    COMPLETED_CONTAINERS=$(az container list --resource-group $RESOURCE_GROUP --query "[?tags.\"genx-case\" && instanceView.state=='Succeeded'].name" --output tsv)
    
    if [ -z "$COMPLETED_CONTAINERS" ]; then
        echo_info "No completed containers to clean up"
        return
    fi
    
    for container in $COMPLETED_CONTAINERS; do
        echo_info "Deleting container: $container"
        az container delete --name $container --resource-group $RESOURCE_GROUP --yes --output none
        echo_success "Deleted: $container"
    done
}

deploy_function() {
    echo_info "Deploying Function App code..."
    
    if [ ! -d "azure-function" ]; then
        echo_error "azure-function directory not found. Run from project root."
        exit 1
    fi
    
    cd azure-function
    
    # Check if func tools are installed
    if ! command -v func &> /dev/null; then
        echo_error "Azure Functions Core Tools not found. Please install:"
        echo "  npm install -g azure-functions-core-tools@4 --unsafe-perm true"
        exit 1
    fi
    
    # Deploy
    func azure functionapp publish $FUNCTION_APP_NAME --python
    
    echo_success "Function deployment complete"
}

list_results() {
    echo_info "Listing results in blob storage..."
    
    STORAGE_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT --query '[0].value' --output tsv)
    
    echo "📊 Results Container Contents:"
    az storage blob list \
        --container-name "results" \
        --account-name $STORAGE_ACCOUNT \
        --account-key "$STORAGE_KEY" \
        --query "[].{Name:name, Size:properties.contentLength, Modified:properties.lastModified}" \
        --output table
}

# Main script logic
case "${1:-help}" in
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    test)
        test_upload
        ;;
    containers)
        list_containers
        ;;
    clean)
        clean_containers
        ;;
    deploy)
        deploy_function
        ;;
    results)
        list_results
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
