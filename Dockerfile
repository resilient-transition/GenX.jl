FROM julia:1.11-bullseye

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Azure CLI for blob storage access
RUN apt-get update && apt-get install -y \
    curl \
    gpg \
    lsb-release \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Julia dependencies first
RUN echo "Setting up Julia environment..."
COPY Project.toml Manifest.toml* ./
RUN julia --project=. -e "using Pkg; Pkg.instantiate()"

# Copy source code
RUN echo "Copying files..."
COPY src/ ./src/
COPY example_systems/ /tmp/example_systems/
RUN chmod -R a+rX /tmp/example_systems/
COPY Run.jl ./Run.jl
#COPY startup.sh /startup.sh
#RUN chmod +x /startup.sh

# Set environment variables
ENV JULIA_NUM_THREADS=4
ENV JULIA_PROJECT=@.
ENV GENX_PRECOMPILE=false

# Default command
CMD julia --project=. Run.jl "$@"