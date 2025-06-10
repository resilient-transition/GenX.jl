# Use the official Julia Docker image with a specific version for reproducibility
FROM julia:1.11

# Set the working directory
WORKDIR /app

# Set environment variable to disable GenX precompilation
ENV GENX_PRECOMPILE=false

# Copy only the required files and folders
COPY src/ ./src/
COPY example_systems/1_three_zones/ ./example_systems/1_three_zones/
COPY Project.toml .
COPY pyproject.toml .
COPY Run.jl .

# Install Julia dependencies
RUN julia --project=. -e "using Pkg; Pkg.instantiate(); Pkg.precompile()"

# Set the default command to run the GenX case
CMD ["julia", "--project=.", "Run.jl", "./example_systems/1_three_zones"]
