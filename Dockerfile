FROM runpod/worker-comfyui:5.7.1-base

# Set working directory
WORKDIR /comfyui

# Install required Python packages
RUN pip install --no-cache-dir \
    huggingface-hub \
    accelerate \
    safetensors \
    fastapi \
    uvicorn

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
    mkdir -p /comfyui/models/clip && \
    mv /tmp/qwen-models/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors \
       /comfyui/models/clip/

# UNET/Diffusion Model - FP8 Quantized (19 GB, ~50% smaller than BF16)
RUN python3 -c "from huggingface_hub import hf_hub_download; \
    hf_hub_download( \
        repo_id='drbaph/Qwen-Image-Edit-2511-FP8', \
        filename='qwen_image_edit_2511_fp8_e4m3fn.safetensors', \
        local_dir='/tmp/qwen-edit-models', \
        local_dir_use_symlinks=False \
    )" && \
    mkdir -p /comfyui/models/unet && \
    mv /tmp/qwen-edit-models/qwen_image_edit_2511_fp8_e4m3fn.safetensors \
       /comfyui/models/unet/

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

# Upscale Models
RUN mkdir -p /comfyui/models/upscale_models && \
    wget -q -O /comfyui/models/upscale_models/4x_NMKD-Superscale-SP_178000_G.pth \
        "https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Superscale-SP_178000_G.pth" && \
    wget -q -O /comfyui/models/upscale_models/1x-ITF-SkinDiffDetail-Lite-v1.pth \
        "https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/1x-ITF-SkinDiffDetail-Lite-v1.pth"

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

# ComfyUI-KJNodes - Required for FluxKontextImageScale, ImageConcanate and other utility nodes
RUN git clone https://github.com/kijai/ComfyUI-KJNodes.git && \
    cd ComfyUI-KJNodes && \
    pip install --no-cache-dir -r requirements.txt || true

# rgthree-comfy - Required for Image Comparer node
RUN git clone https://github.com/rgthree/rgthree-comfy.git || true

# ComfyUI-Easy-Use - Required for easy cleanGpuUsed, easy clearCacheAll nodes
RUN git clone https://github.com/yolain/ComfyUI-Easy-Use.git && \
    cd ComfyUI-Easy-Use && \
    pip install --no-cache-dir -r requirements.txt || true

# ComfyUI_Comfyroll_CustomNodes - Required for Comfyroll nodes
RUN git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git || true

# comfyui_qwen_image_edit_adv - Required for QwenImageEditScale node
RUN git clone https://github.com/lenML/comfyui_qwen_image_edit_adv.git || true

# Note: CFGNorm is a built-in ComfyUI node, no custom node needed

#===============================================================================
# Copy application files
#===============================================================================

WORKDIR /comfyui

# Copy workflow templates
COPY workflow_single.json /workflow_single.json
COPY workflow_couples.json /workflow_couples.json

# Copy handler and load balancer app
COPY handler.py /handler.py
COPY app_lb.py /app_lb.py

#===============================================================================
# Verify installations
#===============================================================================

RUN echo "=== Verifying Model Downloads ===" && \
    ls -lh /comfyui/models/clip/*.safetensors && \
    ls -lh /comfyui/models/unet/*.safetensors && \
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
ENV PORT=5000
ENV PORT_HEALTH=5000

# Run the FastAPI load balancer server
CMD ["python3", "/app_lb.py"]
