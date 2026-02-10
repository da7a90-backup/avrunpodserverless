# RunPod Serverless ComfyUI Deployment

This directory contains the implementation for deploying ComfyUI as a RunPod serverless endpoint.

## Architecture

```
Frontend → Vercel API (/api/generate) → RunPod Serverless Endpoint → ComfyUI → Results
```

**Key Components:**
- `handler.py`: RunPod serverless handler that processes jobs with ComfyUI
- `Dockerfile`: Container image definition
- `setup-network-volume.sh`: Script to set up ComfyUI on RunPod network storage

## Setup Instructions

### 1. Copy Existing ComfyUI to Network Volume

Your current RunPod instance at 38.80.152.72 already has ComfyUI with all models installed at `/workspace/ComfyUI`.

We'll copy this to a RunPod network volume so it can be shared across serverless workers:

```bash
# Option A: Create network volume from existing pod storage (Recommended)
# 1. In RunPod console, go to your current pod
# 2. Click "Convert to Network Volume" or create a snapshot
# 3. This preserves everything: ComfyUI, models, custom nodes

# Option B: Manual rsync (if Option A not available)
# 1. Create a new network volume in RunPod console
#    Name: comfyui-storage
#    Size: 200GB+ (to fit your 38GB model + others)
#
# 2. Launch a temporary pod with BOTH:
#    - Your existing pod's storage mounted
#    - The new network volume attached at /runpod-volume
#
# 3. Copy everything:
rsync -avP /workspace/ComfyUI/ /runpod-volume/ComfyUI/

# 4. Verify the copy
ls -lh /runpod-volume/ComfyUI/models/checkpoints/
# Should see: qwen_image_edit_2511_bf16.safetensors (38GB)

# 5. Copy workflow templates
cp /workspace/ComfyUI/workflow_single.json /runpod-volume/ComfyUI/
cp /workspace/ComfyUI/workflow_couples.json /runpod-volume/ComfyUI/
```

**Important**: The Docker image does NOT contain ComfyUI or models - it only has the handler. This keeps the image <1GB and builds in seconds.

### 2. Build and Push Docker Image

```bash
cd /Users/guertethiaf/Downloads/dontdelete/Don/runpod-serverless

# Build the image
docker build -t your-dockerhub-username/comfyui-runpod:latest .

# Push to Docker Hub (or any container registry)
docker push your-dockerhub-username/comfyui-runpod:latest
```

### 3. Create RunPod Serverless Endpoint

1. Go to RunPod console → Serverless
2. Click "Create Endpoint"
3. Configure:
   - **Name**: comfyui-serverless
   - **Docker Image**: `your-dockerhub-username/comfyui-runpod:latest`
   - **Network Volume**: Select `comfyui-storage` (mount at `/runpod-volume`)
   - **GPU**: Select desired GPU (e.g., RTX 4090, A40, A100)
   - **Workers**: Set min=0, max=3 (adjust based on needs)
   - **Max Execution Time**: 300 seconds (5 minutes)
   - **Container Disk**: 20GB

4. Optional - Configure Model Caching:
   - If you're using models from Hugging Face, add them in the "Model Caching" section
   - Example: `stabilityai/stable-diffusion-xl-base-1.0`

5. Deploy the endpoint

6. Note the endpoint ID and URL from the console

### 4. Update Vercel API

Update your Vercel environment variables:

```bash
# Add to Vercel project settings or .env.local
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_ENDPOINT_ID=your_endpoint_id
```

Create new API route: `/api/runpod/generate/route.ts`

See implementation details in the Vercel API update task.

## Testing

Test the handler locally with RunPod CLI:

```bash
# Install RunPod CLI
pip install runpod

# Test handler
python test_handler.py
```

## Input Format

The handler expects:

```json
{
  "input": {
    "jobId": "uuid-string",
    "styleId": "single",
    "userImage1Url": "https://vercel-blob-url/user1.png",
    "userImage2Url": "https://vercel-blob-url/user2.png",
    "referenceImageUrl": "https://vercel-blob-url/reference.png",
    "prompt": "A photo in the style of..."
  }
}
```

## Output Format

```json
{
  "status": "completed",
  "jobId": "uuid-string",
  "images": [
    "base64_encoded_image_1",
    "base64_encoded_image_2"
  ],
  "message": "Generated 2 images successfully"
}
```

## Benefits vs Lambda Labs

✅ **No instance management** - Auto-scaling from 0 to N workers
✅ **Pay per second** - Only charged for actual processing time
✅ **Faster cold starts** - Model caching + network volume
✅ **Simpler code** - No polling, QStash, or instance lifecycle
✅ **Built-in monitoring** - RunPod dashboard shows all metrics

## Cost Comparison

**Lambda Labs (current):**
- $1.10/hour for RTX A6000 even when idle
- Manual instance management
- ~$26.40/day if running 24/7

**RunPod Serverless:**
- $0.000308/second for RTX 4090 (only when processing)
- Typical job: 30 seconds = $0.00924
- 100 jobs/day = $0.92/day
- **96% cost savings** for typical workload!

## Troubleshooting

**Cold Start Issues:**
- First request may take 30-60 seconds to start ComfyUI
- Subsequent requests are fast (<2s)
- Use RunPod's active worker setting to keep 1 worker warm

**Model Loading:**
- Ensure models are in correct paths under `/runpod-volume/ComfyUI/models/`
- Check handler logs in RunPod dashboard

**Timeout Errors:**
- Increase `maxDuration` if jobs take longer than 5 minutes
- Check ComfyUI logs for actual errors

## Migration Checklist

- [x] Review existing Lambda integration
- [x] Review RunPod serverless documentation
- [x] Design RunPod serverless architecture
- [ ] Set up ComfyUI on RunPod network storage
- [ ] Create and test handler locally
- [ ] Build and push Docker image
- [ ] Create RunPod serverless endpoint
- [ ] Update Vercel API to use RunPod
- [ ] Test end-to-end flow
- [ ] Migrate production traffic
- [ ] Terminate Lambda instances
