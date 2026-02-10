FROM python:3.10-slim

# Set working directory
WORKDIR /

# Install handler dependencies
RUN pip install --no-cache-dir runpod requests websocket-client

# Copy handler
COPY handler.py /handler.py

# Verify runpod is installed
RUN python -c "import runpod; print(f'RunPod SDK {runpod.__version__} installed successfully')"

# Start handler
CMD ["python", "-u", "/handler.py"]
