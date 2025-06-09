# Parallel GenX Jobs on Azure Container Apps

This workflow enables running multiple GenX cases in parallel using Azure Container Apps, providing better scalability and resource management than GitHub Actions.

## How Parallel Execution Works

### **Answer to your question: YES, this runs jobs in parallel!**

The workflow uses GitHub Actions **matrix strategy** to:
1. **Parse multiple case names** from comma-separated input
2. **Create parallel Container App jobs** - one for each case
3. **Run up to N jobs simultaneously** (configurable max_parallel)
4. **Monitor each job independently**
5. **Collect results from all jobs**

## Workflow Architecture

```
Input: "case1,case2,case3,case4,case5"
       ↓
┌─────────────────────────────────────┐
│     GitHub Actions Matrix           │
│  ┌─────┬─────┬─────┬─────┬─────┐   │
│  │Job 1│Job 2│Job 3│Job 4│Job 5│   │  (max_parallel=5)
│  │case1│case2│case3│case4│case5│   │
│  └─────┴─────┴─────┴─────┴─────┘   │
└─────────────────────────────────────┘
       ↓ (parallel execution)
┌─────────────────────────────────────┐
│       Azure Container Apps          │
│  ┌─────┬─────┬─────┬─────┬─────┐   │
│  │ACA 1│ACA 2│ACA 3│ACA 4│ACA 5│   │  (separate containers)
│  │GenX │GenX │GenX │GenX │GenX │   │
│  └─────┴─────┴─────┴─────┴─────┘   │
└─────────────────────────────────────┘
       ↓ (results uploaded)
┌─────────────────────────────────────┐
│        Azure Blob Storage           │
│  results/case1_20241209_143022/     │
│  results/case2_20241209_143025/     │
│  results/case3_20241209_143028/     │
│  results/case4_20241209_143031/     │
│  results/case5_20241209_143034/     │
└─────────────────────────────────────┘
```

## Usage Examples

### Example 1: Run 3 cases in parallel
```
# Manual trigger in GitHub Actions:
case_names: "kentucky,texas,california"
max_parallel: 3
cpu_cores: 1.0
memory_gb: 2.0
```

**Result**: 3 Container App jobs run simultaneously, each with 1 CPU core and 2GB RAM.

### Example 2: Run 10 cases with resource limits
```
case_names: "case1,case2,case3,case4,case5,case6,case7,case8,case9,case10"
max_parallel: 5
cpu_cores: 2.0
memory_gb: 4.0
```

**Result**: 5 jobs run first, then 5 more jobs start as the first batch completes. Each job gets 2 CPU cores and 4GB RAM.

### Example 3: Large batch processing
```
case_names: "region1,region2,region3,region4,region5,region6,region7,region8,region9,region10,region11,region12"
max_parallel: 6
cpu_cores: 1.5
memory_gb: 3.0
```

**Result**: Runs 6 jobs at a time in 2 waves (6 + 6), with moderate resource allocation.

## Resource Management

### **Per-Job Resources**
- **CPU**: 0.25 to 2.0 cores per job
- **Memory**: 0.5 to 4.0 GB per job
- **Storage**: Temporary disk for downloads/processing
- **Timeout**: 2 hours per job (configurable)

### **Total Resource Usage**
If you run 5 parallel jobs with 2 cores and 4GB each:
- **Total**: 10 CPU cores, 20GB RAM
- **Cost**: Pay only for actual usage time
- **Scaling**: Automatic scale-to-zero when jobs complete

## Advantages over GitHub Actions

| Feature | GitHub Actions | Azure Container Apps |
|---------|----------------|---------------------|
| **Max Runtime** | 6 hours | Unlimited |
| **CPU Cores** | 2 cores | Up to 2 cores per job |
| **Memory** | 7GB | Up to 4GB per job |
| **Parallel Jobs** | 20 (org limit) | Hundreds |
| **Cost** | Free tier limited | Pay-per-use |
| **GPU Support** | No | Yes (preview) |
| **Network** | GitHub's | Azure's high-speed |
| **Storage** | Temporary | Persistent options |

## Setup Instructions

### 1. Required Azure Resources

```bash
# Create resource group
az group create --name genx-rg --location eastus

# The workflow will auto-create:
# - Container App Environment
# - Azure Container Registry
# - Container App Jobs
```

### 2. GitHub Secrets

Add these secrets to your repository:

```
AZURE_CREDENTIALS='{"clientId":"...","clientSecret":"...","subscriptionId":"...","tenantId":"..."}'
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_RESOURCE_GROUP=genx-rg
AZURE_LOCATION=eastus
AZURE_STORAGE_ACCOUNT=genxstor25501
AZURE_STORAGE_KEY=your-storage-key
```

### 3. Blob Storage Structure

```
genx-data/
├── inputs/
│   ├── kentucky/
│   │   ├── settings/
│   │   ├── system/
│   │   └── resources/
│   ├── texas/
│   └── california/
└── results/
    ├── kentucky_20241209_143022/
    ├── texas_20241209_143025/
    └── california_20241209_143028/
```

## Monitoring and Troubleshooting

### Real-time Monitoring

1. **GitHub Actions UI**: Shows overall progress
2. **Azure Portal**: Container Apps → Jobs → Executions
3. **Azure CLI**: 
   ```bash
   az containerapp job execution list --job-name genx-case1-1234567890 --resource-group genx-rg
   ```

### Logs and Debugging

- **GitHub Actions**: Each matrix job has separate logs
- **Container Apps**: Real-time streaming logs
- **Artifacts**: Failed job logs uploaded as GitHub artifacts

### Common Issues

1. **Resource Limits**: Reduce `max_parallel` or resource allocation
2. **Timeout**: Increase timeout in workflow (default: 2 hours)
3. **Image Build**: First run takes longer due to container build
4. **Cost**: Monitor Azure costs in billing dashboard

## Cost Optimization

### Strategies

1. **Right-size resources**: Start with 1 core, 2GB, scale up if needed
2. **Batch processing**: Group smaller cases together
3. **Time-based runs**: Use cheaper regions/times
4. **Auto-cleanup**: Workflow deletes completed jobs (optional)

### Example Costs (East US, approximate)

- **Small job** (1 core, 2GB, 30 min): ~$0.10
- **Medium job** (2 cores, 4GB, 60 min): ~$0.40
- **Large job** (2 cores, 4GB, 120 min): ~$0.80

## Comparison: Serial vs Parallel

### Serial Execution (Original)
```
Total time = Case1 (60min) + Case2 (60min) + Case3 (60min) = 180 minutes
Total cost = 3 × $0.40 = $1.20
```

### Parallel Execution (New)
```
Total time = max(Case1, Case2, Case3) = 60 minutes
Total cost = 3 × $0.40 = $1.20 (same cost, 3x faster!)
```

## Next Steps

1. **Test with 2-3 small cases** first
2. **Monitor resource usage** and adjust
3. **Scale up** to larger batches
4. **Set up Event Grid** for automatic triggering
5. **Consider GPU instances** for very large models

The parallel workflow gives you **true scalability** - run dozens of GenX cases simultaneously with proper resource isolation and cost control!

