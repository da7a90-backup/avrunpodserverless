FROM runpod/worker-comfyui:5.7.1-base

# Override extra_model_paths.yaml to use network volume
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# The base image already has the correct handler and start.sh
# No need to override CMD - it will use /start.sh from the base image
