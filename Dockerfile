FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

# Set working directory
WORKDIR /

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install ComfyUI dependencies (torch already in base image)
RUN pip install --no-cache-dir \
    runpod requests websocket-client \
    pillow numpy scipy \
    transformers tokenizers sentencepiece \
    safetensors aiohttp pyyaml tqdm psutil \
    torchvision

# Copy handler
COPY handler.py /handler.py

# Verify installations
RUN python -c "import runpod; import torch; import PIL; print('All dependencies installed')"

# Start handler
CMD ["python", "-u", "/handler.py"]
