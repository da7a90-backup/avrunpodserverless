FROM runpod/worker-comfyui:5.7.1-base

# Override extra_model_paths.yaml to use network volume
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Replace the default handler with our custom one (start.sh will call /handler.py)
COPY handler.py /handler.py

# Use the default CMD from base image which runs /start.sh
# /start.sh starts ComfyUI and then runs /handler.py
