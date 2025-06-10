#!/bin/bash
# Complete deployment script for GenX Azure infrastructure
# This script deploys the entire GenX cloud processing system

set -euo pipefail

# Configuration
RESOURCE_GROUP="genx-rg"
LOCATION="eastus"
STORAGE_ACCOUNT="genxstorage$(date +%s | tail -c 6)"
REGISTRY_NAME="genxjlregistry$(date +%s | tail -c 6)"
FUNCTION_APP="genx-function-$(date +%s | tail -c 6)"
APP_INSIGHTS="genx-insights-$(date +%s | tail -c 6)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

echo_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

show_banner() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                   GenX Event Grid Automation                ║"
    echo "║                 Complete Deployment Guide                   ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    echo_step "Checking prerequisites..."
    
    local all_good=true
    
    # Check Azure CLI
    if command -v az &> /dev/null; then
        echo_success "Azure CLI is installed"
        if az account show &> /dev/null; then
            SUBSCRIPTION=$(az account show --query name --output tsv)
            echo_success "Logged into Azure: $SUBSCRIPTION"
        else
            echo_error "Please login to Azure: az login"
            all_good=false
        fi
    else
        echo_error "Azure CLI not installed. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        all_good=false
    fi
    
    # Check Docker
    if command -v docker &> /dev/null; then
        echo_success "Docker is installed"
    else
        echo_error "Docker not installed. Please install: https://docs.docker.com/get-docker/"
        all_good=false
    fi
    
    # Check Python
    if command -v python3 &> /dev/null; then
        echo_success "Python 3 is installed"
    else
        echo_error "Python 3 not installed"
        all_good=false
    fi
    
    # Check Azure Functions Core Tools
    if command -v func &> /dev/null; then
        echo_success "Azure Functions Core Tools installed"
    else
        echo_warning "Azure Functions Core Tools not installed"
        echo_info "Install with: npm install -g azure-functions-core-tools@4 --unsafe-perm true"
    fi
    
    if [ "$all_good" = false ]; then
        echo_error "Please install missing prerequisites and try again"
        exit 1
    fi
}

validate_setup() {
    echo_step "Validating GenX Event Grid setup..."
    
    if python3 scripts/validate_setup.py; then
        echo_success "Setup validation passed"
    else
        echo_error "Setup validation failed"
        exit 1
    fi
}

show_deployment_plan() {
    echo_step "Deployment Plan"
    echo ""
    echo "This script will:"
    echo "  1. ✅ Validate prerequisites and setup"
    echo "  2. 🏗️  Deploy Azure infrastructure (Resource Group, Storage, Function App, Event Grid)"
    echo "  3. 🐳 Build and push GenX containers to Azure Container Registry"
    echo "  4. ⚡ Deploy Azure Function code"
    echo "  5. 🧪 Test the complete workflow"
    echo "  6. 📊 Show monitoring information"
    echo ""
    read -p "Continue with deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled"
        exit 0
    fi
}

deploy_infrastructure() {
    echo_step "Deploying Azure infrastructure..."
    
    if ./scripts/setup_event_grid.sh; then
        echo_success "Infrastructure deployment completed"
    else
        echo_error "Infrastructure deployment failed"
        exit 1
    fi
}

build_and_push_containers() {
    echo_step "Building and pushing GenX containers..."
    
    # Login to ACR
    az acr login --name genxjlregistry
    
    # Build and push original GenX container
    echo_info "Building original GenX container..."
    docker build --platform linux/amd64 -t genxjlregistry.azurecr.io/genx-jl:latest .
    docker push genxjlregistry.azurecr.io/genx-jl:latest
    
    # Build and push Event Grid container
    echo_info "Building Event Grid GenX container..."
    docker build --platform linux/amd64 -f Dockerfile.eventgrid -t genxjlregistry.azurecr.io/genx-eventgrid:latest .
    docker push genxjlregistry.azurecr.io/genx-eventgrid:latest
    
    echo_success "Containers built and pushed to ACR"
}

deploy_function() {
    echo_step "Deploying Azure Function..."
    
    cd azure-function
    
    if command -v func &> /dev/null; then
        if func azure functionapp publish genx-eventgrid-function --python; then
            echo_success "Function deployed successfully"
        else
            echo_error "Function deployment failed"
            exit 1
        fi
    else
        echo_warning "Azure Functions Core Tools not installed"
        echo_info "Please install and deploy manually:"
        echo_info "  npm install -g azure-functions-core-tools@4 --unsafe-perm true"
        echo_info "  cd azure-function"
        echo_info "  func azure functionapp publish genx-eventgrid-function"
    fi
    
    cd ..
}

test_workflow() {
    echo_step "Testing the complete workflow..."
    
    if ./scripts/monitor_deployment.sh test; then
        echo_success "Workflow test initiated"
        echo_info "Monitor the processing with: ./scripts/monitor_deployment.sh logs"
    else
        echo_error "Workflow test failed"
    fi
}

show_summary() {
    echo_step "Deployment Summary"
    echo ""
    echo_success "GenX Event Grid Automation is now deployed! 🎉"
    echo ""
    echo "📋 What was deployed:"
    echo "  • Azure Resource Group: genx-rg"
    echo "  • Storage Account: genxstorage (with cases/ and results/ containers)"
    echo "  • Function App: genx-eventgrid-function"
    echo "  • Container Registry: genxjlregistry"
    echo "  • Event Grid subscription for blob events"
    echo ""
    echo "🔗 Important URLs:"
    echo "  • Function App: https://genx-eventgrid-function.azurewebsites.net"
    echo "  • Status Endpoint: https://genx-eventgrid-function.azurewebsites.net/api/status"
    echo "  • Storage Account: https://genxstorage.blob.core.windows.net"
    echo ""
    echo "🛠️  Management Commands:"
    echo "  • Check status: ./scripts/monitor_deployment.sh status"
    echo "  • Stream logs: ./scripts/monitor_deployment.sh logs"
    echo "  • Test system: ./scripts/monitor_deployment.sh test"
    echo "  • List results: ./scripts/monitor_deployment.sh results"
    echo ""
    echo "📁 How to use:"
    echo "  1. Upload GenX case to 'cases/' container in blob storage"
    echo "  2. System automatically detects upload and processes case"
    echo "  3. Results appear in 'results/' container when complete"
    echo ""
    echo "📚 Documentation:"
    echo "  • Complete guide: COMPLETE_WORKFLOW_GUIDE.md"
    echo "  • Detailed setup: EVENT_GRID_README.md"
    echo ""
    echo_success "Ready for GenX automation! 🚀"
}

main() {
    show_banner
    check_prerequisites
    validate_setup
    show_deployment_plan
    deploy_infrastructure
    build_and_push_containers
    deploy_function
    test_workflow
    show_summary
}

# Run main function
main "$@"
