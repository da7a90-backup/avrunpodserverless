FROM runpod/worker-comfyui:latest-base

# Copy our custom handler that uses ComfyUI from network volume
COPY handler.py /handler.py

# Start handler
CMD ["python3", "-u", "/handler.py"]
