#!/bin/bash
set -e

echo "=== GenX Container Startup ==="
echo "Timestamp: $(date)"
echo "Case: $CASE_NAME"
echo "Container: $BLOB_CONTAINER"

# Validate required environment variables
if [ -z "$AZURE_STORAGE_ACCOUNT" ] || [ -z "$AZURE_STORAGE_KEY" ] || [ -z "$BLOB_CONTAINER" ] || [ -z "$CASE_NAME" ]; then
    echo "ERROR: Missing required environment variables"
    echo "Required: AZURE_STORAGE_ACCOUNT, AZURE_STORAGE_KEY, BLOB_CONTAINER, CASE_NAME"
    exit 1
fi

# Set Azure Storage connection string
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=$AZURE_STORAGE_ACCOUNT;AccountKey=$AZURE_STORAGE_KEY;EndpointSuffix=core.windows.net"

echo "=== Downloading Input Data ==="
# Create case input directory
mkdir -p /genx/case_input

# Download case data from blob storage
# Expected structure: inputs/{CASE_NAME}/
echo "Downloading case data for: $CASE_NAME"
az storage blob download-batch \
    --source "$BLOB_CONTAINER" \
    --destination /genx/case_input \
    --pattern "inputs/${CASE_NAME}/*" \
    --connection-string "$AZURE_STORAGE_CONNECTION_STRING"

# Check if data was downloaded
if [ ! -d "/genx/case_input/inputs/$CASE_NAME" ]; then
    echo "ERROR: No input data found for case: $CASE_NAME"
    echo "Expected path: inputs/$CASE_NAME/ in container $BLOB_CONTAINER"
    exit 1
fi

echo "Input data downloaded successfully"
ls -la /genx/case_input/inputs/$CASE_NAME/

echo "=== Setting up Case Directory ==="
# Create a symlink or copy the case to the expected location
# GenX expects the case to be in the current directory
CASE_PATH="/genx/case_input/inputs/$CASE_NAME"
if [ -d "$CASE_PATH" ]; then
    # Copy case files to working directory
    cp -r "$CASE_PATH"/* /genx/
    echo "Case files copied to working directory"
else
    echo "ERROR: Case directory not found: $CASE_PATH"
    exit 1
fi

echo "=== Running GenX Model ==="
echo "Julia version: $(julia --version)"
echo "Working directory: $(pwd)"
echo "Case files:"
ls -la

# Set Julia environment
export JULIA_PROJECT=/genx

# Run GenX
echo "Starting GenX execution..."
start_time=$(date +%s)

julia --project=/genx Run.jl

end_time=$(date +%s)
execution_time=$((end_time - start_time))
echo "GenX execution completed in $execution_time seconds"

echo "=== Processing Results ==="
# Create results directory with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULT_DIR="${CASE_NAME}_${TIMESTAMP}"
mkdir -p /genx/case_output/$RESULT_DIR

# Copy results (GenX typically outputs to current directory)
# Common GenX output files
if [ -d "results" ]; then
    cp -r results/* /genx/case_output/$RESULT_DIR/
fi

# Copy any CSV files (GenX outputs)
find . -name "*.csv" -exec cp {} /genx/case_output/$RESULT_DIR/ \;

# Copy log files if they exist
find . -name "*.log" -exec cp {} /genx/case_output/$RESULT_DIR/ \;

# Copy the Julia project files for reproducibility
cp Project.toml /genx/case_output/$RESULT_DIR/ 2>/dev/null || true
cp Manifest.toml /genx/case_output/$RESULT_DIR/ 2>/dev/null || true

# Create a summary file
cat > /genx/case_output/$RESULT_DIR/execution_summary.txt << EOF
GenX Execution Summary
=====================
Case Name: $CASE_NAME
Container: $BLOB_CONTAINER
Start Time: $(date -d @$start_time)
End Time: $(date -d @$end_time)
Execution Time: $execution_time seconds
Host: $(hostname)
Julia Version: $(julia --version)
GenX Version: $(julia --project=/genx -e "using Pkg; println(Pkg.status())" 2>/dev/null || echo "Unknown")

Output Files:
$(ls -la /genx/case_output/$RESULT_DIR/)
EOF

echo "Results prepared in: $RESULT_DIR"

echo "=== Uploading Results ==="
# Upload results to blob storage
# Upload to: results/{CASE_NAME}_{TIMESTAMP}/
az storage blob upload-batch \
    --source /genx/case_output/$RESULT_DIR \
    --destination "$BLOB_CONTAINER" \
    --destination-path "results/$RESULT_DIR" \
    --connection-string "$AZURE_STORAGE_CONNECTION_STRING"

echo "Results uploaded to: results/$RESULT_DIR"

echo "=== Container Execution Complete ==="
echo "Total execution time: $execution_time seconds"
echo "Results available at: https://$AZURE_STORAGE_ACCOUNT.blob.core.windows.net/$BLOB_CONTAINER/results/$RESULT_DIR"