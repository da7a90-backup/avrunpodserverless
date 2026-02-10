FROM runpod/worker-comfyui:5.7.1-base

# Override extra_model_paths.yaml to use network volume
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Copy workflow templates into the image
COPY workflow_single.json workflow_couples.json /

# Replace the default handler with our custom one
# The base image's /start.sh will start ComfyUI and then run /handler.py
COPY handler.py /handler.py
