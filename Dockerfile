FROM runpod/base:0.4.0-cuda11.8.0

# Set working directory
WORKDIR /

# Install minimal dependencies using python3 -m pip to ensure correct installation
RUN python3 -m pip install --no-cache-dir \
    runpod requests websocket-client \
    && python3 -c "import runpod; print('runpod installed successfully')"

# Copy handler
COPY handler.py /handler.py

# Start handler
CMD ["python3", "-u", "/handler.py"]
