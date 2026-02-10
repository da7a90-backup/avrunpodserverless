FROM runpod/base:0.4.0-cuda11.8.0

# Set working directory
WORKDIR /

# Install minimal dependencies
RUN pip install --no-cache-dir \
    runpod requests websocket-client

# Copy handler
COPY handler.py /handler.py

# Verify installations
RUN python -c "import runpod; import torch; import PIL; print('All dependencies installed')"

# Start handler
CMD ["python", "-u", "/handler.py"]
