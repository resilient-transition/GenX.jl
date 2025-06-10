# Use the official Julia Docker image with a specific version for reproducibility
FROM julia:1.11

# Set the working directory
WORKDIR /app

# Install system dependencies including Python for Azure SDK
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Azure SDK for Python (for blob storage operations)
RUN pip3 install --break-system-packages azure-storage-blob azure-identity

# Set environment variables
ENV GENX_PRECOMPILE=false
ENV JULIA_NUM_THREADS=auto
ENV JULIA_PKG_USE_CLI_GIT=true

# Copy the GenX source code and project files
COPY src/ ./src/
COPY Project.toml .
COPY pyproject.toml .
COPY Run.jl .

# Copy the example system as a fallback (for testing)
COPY example_systems/1_three_zones/ ./example_systems/1_three_zones/

# Copy the enhanced run script that handles blob storage
COPY scripts/run_genx_case.py ./

# Install Julia dependencies
RUN julia --project=. -e "using Pkg; Pkg.instantiate(); Pkg.precompile()" && \
    julia --project=. -e "using Pkg; Pkg.gc()" && \
    rm -rf ~/.julia/logs

# Create directory for dynamic case data
RUN mkdir -p /app/cases

# Set the default command to run with dynamic case handling
# If no case specified via environment variables, falls back to three-zones example
CMD ["python3", "run_genx_case.py"]
