FROM runpod/worker-comfyui:5.7.1-base

# Set working directory
WORKDIR /comfyui

# Install required Python packages
RUN pip install --no-cache-dir \
    huggingface-hub \
    accelerate \
    safetensors

#===============================================================================
# Download all models from HuggingFace at build time
#===============================================================================

# CLIP/Text Encoder Model (9.38 GB)
RUN python3 -c "from huggingface_hub import hf_hub_download; \
    hf_hub_download( \
        repo_id='Comfy-Org/Qwen-Image_ComfyUI', \
        filename='split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors', \
        local_dir='/tmp/qwen-models', \
        local_dir_use_symlinks=False \
    )" && \
    mkdir -p /comfyui/models/text_encoders && \
    mv /tmp/qwen-models/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors \
       /comfyui/models/text_encoders/

# UNET/Diffusion Model (40.9 GB)
RUN python3 -c "from huggingface_hub import hf_hub_download; \
    hf_hub_download( \
        repo_id='Comfy-Org/Qwen-Image-Edit_ComfyUI', \
        filename='split_files/diffusion_models/qwen_image_edit_2511_bf16.safetensors', \
        local_dir='/tmp/qwen-edit-models', \
        local_dir_use_symlinks=False \
    )" && \
    mkdir -p /comfyui/models/diffusion_models && \
    mv /tmp/qwen-edit-models/split_files/diffusion_models/qwen_image_edit_2511_bf16.safetensors \
       /comfyui/models/diffusion_models/

# VAE Model (254 MB)
RUN python3 -c "from huggingface_hub import hf_hub_download; \
    hf_hub_download( \
        repo_id='Comfy-Org/Qwen-Image_ComfyUI', \
        filename='split_files/vae/qwen_image_vae.safetensors', \
        local_dir='/tmp/qwen-models-vae', \
        local_dir_use_symlinks=False \
    )" && \
    mkdir -p /comfyui/models/vae && \
    mv /tmp/qwen-models-vae/split_files/vae/qwen_image_vae.safetensors \
       /comfyui/models/vae/

# BFS Head LoRA - Face Swap LoRA (307 MB)
RUN python3 -c "from huggingface_hub import hf_hub_download; \
    hf_hub_download( \
        repo_id='Alissonerdx/BFS-Best-Face-Swap', \
        filename='bfs_head_v5_2511_merged_version_rank_16_fp16.safetensors', \
        local_dir='/tmp/bfs-lora', \
        local_dir_use_symlinks=False \
    )" && \
    mkdir -p /comfyui/models/loras && \
    mv /tmp/bfs-lora/bfs_head_v5_2511_merged_version_rank_16_fp16.safetensors \
       /comfyui/models/loras/

# Lightning LoRA - Faster generation (850 MB)
RUN python3 -c "from huggingface_hub import hf_hub_download; \
    hf_hub_download( \
        repo_id='lightx2v/Qwen-Image-Edit-2511-Lightning', \
        filename='Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors', \
        local_dir='/tmp/lightning-lora', \
        local_dir_use_symlinks=False \
    )" && \
    mv /tmp/lightning-lora/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors \
       /comfyui/models/loras/ || echo "Lightning LoRA download failed, continuing..."

# Clean up temporary directories
RUN rm -rf /tmp/qwen-models /tmp/qwen-edit-models /tmp/qwen-models-vae /tmp/bfs-lora /tmp/lightning-lora

#===============================================================================
# Install required ComfyUI custom nodes
#===============================================================================

WORKDIR /comfyui/custom_nodes

# ComfyUI-Qwen-Image-Edit - Required for Qwen image editing nodes
RUN git clone https://github.com/kijai/ComfyUI-Qwen-Image-Edit.git && \
    cd ComfyUI-Qwen-Image-Edit && \
    pip install --no-cache-dir -r requirements.txt || true

# ComfyUI-AuraFlow - Required for ModelSamplingAuraFlow node
RUN git clone https://github.com/kijai/ComfyUI-AuraFlow.git && \
    cd ComfyUI-AuraFlow && \
    pip install --no-cache-dir -r requirements.txt || true

# ComfyUI-KJNodes - Required for FluxKontextImageScale and other utility nodes
RUN git clone https://github.com/kijai/ComfyUI-KJNodes.git && \
    cd ComfyUI-KJNodes && \
    pip install --no-cache-dir -r requirements.txt || true

# Note: CFGNorm is a built-in ComfyUI node, no custom node needed

#===============================================================================
# Copy application files
#===============================================================================

WORKDIR /comfyui

# Copy workflow templates
COPY workflow_single.json /workflow_single.json
COPY workflow_couples.json /workflow_couples.json

# Copy handler
COPY handler.py /handler.py

#===============================================================================
# Verify installations
#===============================================================================

RUN echo "=== Verifying Model Downloads ===" && \
    ls -lh /comfyui/models/text_encoders/*.safetensors && \
    ls -lh /comfyui/models/diffusion_models/*.safetensors && \
    ls -lh /comfyui/models/vae/*.safetensors && \
    ls -lh /comfyui/models/loras/*.safetensors && \
    echo "" && \
    echo "=== Verifying Custom Nodes ===" && \
    ls -la /comfyui/custom_nodes/ && \
    echo "" && \
    echo "=== Disk Usage ===" && \
    du -sh /comfyui/models/*

# Set environment variables
ENV COMFYUI_PATH=/comfyui
ENV PYTHONUNBUFFERED=1

# The base image's entrypoint will start ComfyUI and run handler.py
