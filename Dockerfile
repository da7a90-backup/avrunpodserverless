FROM runpod/base:0.4.0-cuda11.8.0

# Set working directory
WORKDIR /

# Install PyTorch with CUDA 11.8 support
RUN python3 -m pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install all other ComfyUI dependencies
RUN python3 -m pip install --no-cache-dir \
    runpod requests websocket-client \
    transformers diffusers accelerate \
    pillow numpy opencv-python \
    aiohttp pyyaml safetensors \
    kornia spandrel soundfile \
    einops scipy psutil \
    sqlalchemy pydantic fastapi \
    && python3 -c "import runpod; import torch; print('Dependencies installed successfully')"

# Copy handler
COPY handler.py /handler.py

# Start handler
CMD ["python3", "-u", "/handler.py"]
