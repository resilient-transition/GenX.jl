# Multi-stage build for GenX.jl with Azure Blob Storage integration
FROM julia:1.11 as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /genx

# Copy Julia project files
COPY Project.toml Manifest.toml ./

# Install Julia dependencies
RUN julia -e "using Pkg; Pkg.instantiate(); Pkg.precompile()"

# Final stage
FROM julia:1.11

# Install system dependencies including Azure CLI
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    unzip \
    python3 \
    python3-pip \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for Azure Blob Storage
RUN pip3 install azure-storage-blob azure-identity

# Set working directory
WORKDIR /genx

# Copy Julia environment from builder
COPY --from=builder /usr/local/julia /usr/local/julia
COPY --from=builder /genx ./

# Copy application code
COPY src/ ./src/
COPY Run.jl ./
COPY startup.sh ./

# Copy any required settings
COPY __base_settings__/ ./__base_settings__/

# Make startup script executable
RUN chmod +x startup.sh

# Set environment variables
ENV JULIA_PROJECT=/genx
ENV JULIA_DEPOT_PATH=/usr/local/julia

# Create directories for input/output
RUN mkdir -p /genx/case_input /genx/case_output

# Use startup script as entrypoint
CMD ["/genx/startup.sh"]