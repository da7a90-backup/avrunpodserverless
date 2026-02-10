FROM python:3.10-slim

# Set working directory
WORKDIR /

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install ComfyUI dependencies (matching the network volume installation)
RUN pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir \
    runpod requests websocket-client \
    pillow numpy scipy \
    transformers tokenizers sentencepiece \
    safetensors aiohttp pyyaml tqdm psutil

# Copy handler
COPY handler.py /handler.py

# Verify installations
RUN python -c "import runpod; import torch; import PIL; print('All dependencies installed')"

# Start handler
CMD ["python", "-u", "/handler.py"]
