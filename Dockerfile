FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Install Python 3.11 and pip
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set python3 to point to python3.11
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Install Python dependencies
RUN pip3 install --no-cache-dir \
    runpod \
    requests \
    websocket-client

# Set working directory
WORKDIR /

# Copy handler
COPY handler.py /handler.py

# Start handler
CMD ["python3", "-u", "/handler.py"]
