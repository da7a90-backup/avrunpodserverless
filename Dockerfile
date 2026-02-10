FROM runpod/base:0.4.0-cuda11.8.0

# Set working directory
WORKDIR /

# Install all ComfyUI dependencies during build
RUN python3 -m pip install --no-cache-dir \
    runpod requests websocket-client \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 \
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
