FROM runpod/worker-comfyui:5.7.1-base

# Override extra_model_paths.yaml to use network volume
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# Copy our custom handler that loads workflows from network volume
COPY handler.py /handler.py

# Override CMD to use our custom handler instead of the default
CMD ["python3", "-u", "/handler.py"]
