FROM runpod/worker-comfyui:5.7.1-base

# Copy our custom handler that uses ComfyUI from network volume
COPY handler.py /handler.py

# Start our custom handler instead of the default
CMD ["python3", "-u", "/handler.py"]
