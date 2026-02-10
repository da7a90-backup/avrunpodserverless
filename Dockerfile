FROM runpod/worker-comfyui:latest-base

# Set working directory
WORKDIR /

# Copy our custom handler
COPY handler.py /handler.py

# Start handler
CMD ["python3", "-u", "/handler.py"]
