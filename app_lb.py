#!/usr/bin/env python3
"""
RunPod Load Balancer Worker for ComfyUI Image Generation
Provides direct HTTP access without queuing infrastructure
"""

import os
import json
import time
import base64
import asyncio
import requests
import subprocess
import signal
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

# Thread pool for running blocking generation work without blocking the event loop.
# This keeps /ping health checks responsive while ComfyUI is generating.
_executor = ThreadPoolExecutor(max_workers=4)

# Import existing handler logic
from handler import (
    upload_image,
    load_workflow_template,
    prepare_workflow,
    queue_prompt,
    wait_for_completion
)

# Configuration
PORT = int(os.environ.get("PORT", 5000))
PORT_HEALTH = int(os.environ.get("PORT_HEALTH", 5000))
COMFYUI_URL = "http://127.0.0.1:8188"

# Global state
comfyui_process = None
comfyui_ready = False
request_count = 0
app = FastAPI(title="ComfyUI Load Balancer Worker")


# Request/Response models
class GenerateRequest(BaseModel):
    jobId: str
    styleId: str
    userImage1Url: str
    referenceImageUrl: str
    prompt: str
    userImage2Url: Optional[str] = None


class GenerateResponse(BaseModel):
    success: bool
    images: Optional[list] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


def start_comfyui():
    """Start ComfyUI server in background and monitor readiness"""
    global comfyui_process, comfyui_ready

    print("Starting ComfyUI server...")
    comfyui_process = subprocess.Popen(
        ["python3", "/comfyui/main.py", "--listen", "127.0.0.1", "--port", "8188"],
    )
    print(f"ComfyUI process started with PID {comfyui_process.pid}")

    # Wait for ComfyUI to be ready (non-blocking startup)
    # Increased timeout to 180s to allow time for large models to load on RunPod
    max_retries = 180
    for i in range(max_retries):
        try:
            response = requests.get(f"{COMFYUI_URL}/system_stats", timeout=2)
            if response.status_code == 200:
                comfyui_ready = True
                print(f"✓ ComfyUI ready after {i+1} seconds")
                return True
        except Exception:
            time.sleep(1)

    raise Exception(f"ComfyUI failed to start within {max_retries} seconds")


def wait_for_comfyui_ready(timeout=120):
    """Wait for ComfyUI to become ready (for use in /generate endpoint)"""
    start = time.time()
    while time.time() - start < timeout:
        if comfyui_ready:
            return True
        time.sleep(0.5)
    raise Exception(f"ComfyUI not ready after {timeout} seconds")


def shutdown_handler(signum, frame):
    """Handle graceful shutdown"""
    print("Shutting down...")
    if comfyui_process:
        comfyui_process.terminate()
        comfyui_process.wait()
    sys.exit(0)


# Register shutdown handlers
signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


@app.on_event("startup")
async def startup_event():
    """Initialize ComfyUI on startup"""
    try:
        start_comfyui()
    except Exception as e:
        print(f"ERROR starting ComfyUI: {e}")
        raise


@app.get("/ping")
async def health_check():
    """
    Health check endpoint for RunPod load balancer.

    Returns:
    - 204: Server is up but ComfyUI is still initializing
    - 200: ComfyUI is fully ready and can accept requests

    RunPod measures cold start time from first 204 to first 200.
    """
    from fastapi.responses import Response

    if comfyui_ready:
        # Worker is fully ready
        return {"status": "healthy", "comfyui": "ready"}
    else:
        # Worker is initializing
        return Response(status_code=204)


@app.get("/ready")
async def readiness_check():
    """
    Readiness check endpoint - returns actual ComfyUI status.
    Use this for debugging, not for RunPod health checks.
    """
    if comfyui_ready:
        return {
            "status": "ready",
            "comfyui": "ready",
            "message": "ComfyUI is fully initialized and ready to process requests"
        }
    else:
        return {
            "status": "starting",
            "comfyui": "initializing",
            "message": "ComfyUI is still starting up, please wait..."
        }


@app.get("/stats")
async def get_stats():
    """Statistics endpoint"""
    return {
        "total_requests": request_count,
        "comfyui_status": "running" if comfyui_process and comfyui_process.poll() is None else "stopped"
    }


def _blocking_generate(request: GenerateRequest) -> GenerateResponse:
    """
    Synchronous generation logic — runs in a thread pool via run_in_executor.
    Keeping this sync means time.sleep() in wait_for_completion only blocks its
    own thread, NOT the FastAPI event loop, so /ping health checks stay responsive.
    """
    start_time = time.time()

    try:
        # Wait for ComfyUI to be ready (if still starting up)
        if not comfyui_ready:
            print(f"⏳ ComfyUI still starting, waiting for readiness...")
            wait_for_comfyui_ready(timeout=120)
            print(f"✓ ComfyUI is now ready")

        print(f"\n=== Processing job {request.jobId} ===")
        print(f"Style: {request.styleId}")
        print(f"Input URLs:")
        print(f"  referenceImageUrl (style) = {request.referenceImageUrl}")
        print(f"  userImage1Url (face) = {request.userImage1Url}")
        if request.userImage2Url:
            print(f"  userImage2Url (face 2) = {request.userImage2Url}")

        # Upload images to ComfyUI
        print("Uploading reference image to ComfyUI...")
        reference_image_name = upload_image(request.referenceImageUrl, "reference.png")

        print("Uploading user image 1 to ComfyUI...")
        user_image1_name = upload_image(request.userImage1Url, "user1.png")

        user_image2_name = None
        if request.userImage2Url:
            print("Uploading user image 2 to ComfyUI...")
            user_image2_name = upload_image(request.userImage2Url, "user2.png")

        # Load and prepare workflow
        print("Loading workflow template...")
        is_couples = request.styleId == 'couples'
        workflow = load_workflow_template(request.styleId)

        print("Preparing workflow...")
        workflow = prepare_workflow(
            workflow,
            reference_image_name,
            user_image1_name,
            user_image2_name,
            request.prompt,
            is_couples
        )

        # Queue prompt
        client_id = str(uuid.uuid4())
        print(f"Queueing prompt with client_id {client_id}...")
        prompt_id = queue_prompt(workflow, client_id)

        print(f"Prompt queued with ID {prompt_id}, waiting for completion...")

        # Wait for results (using same timeout as handler.py)
        result_images = wait_for_completion(prompt_id, timeout=900)

        print(f"Workflow completed, got {len(result_images)} images")

        # Encode images as base64
        encoded_images = []
        for img_data in result_images:
            encoded = base64.b64encode(img_data).decode('utf-8')
            encoded_images.append(encoded)

        execution_time = time.time() - start_time
        print(f"✓ Job {request.jobId} completed in {execution_time:.2f}s")

        return GenerateResponse(
            success=True,
            images=encoded_images,
            execution_time=execution_time
        )

    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = str(e)
        print(f"✗ Job {request.jobId} failed after {execution_time:.2f}s: {error_msg}")
        import traceback
        traceback.print_exc()

        return GenerateResponse(
            success=False,
            error=error_msg,
            execution_time=execution_time
        )


@app.post("/generate")
async def generate(request: GenerateRequest):
    """
    Main generation endpoint — returns Server-Sent Events (SSE) stream.

    Streams keep-alive heartbeats every 15 seconds while ComfyUI generates.
    This prevents Cloudflare's ~100s idle timeout from closing the connection
    before generation completes (which was causing 502 Bad Gateway errors).

    The stream ends with a single 'data: {...}' JSON event containing the result.
    The client should read lines until it gets a line starting with 'data: ',
    then parse that line as JSON to get the GenerateResponse.
    """
    global request_count
    request_count += 1

    loop = asyncio.get_event_loop()
    # Submit blocking generation to thread pool immediately
    future = loop.run_in_executor(_executor, _blocking_generate, request)

    async def sse_stream():
        # Send keep-alive SSE comments every 15s while generation runs.
        # SSE comment lines (starting with ':') are ignored by EventSource clients
        # but keep the TCP connection alive through Cloudflare's proxy.
        while not future.done():
            yield ": keep-alive\n\n"
            # Wait 15 seconds, but check every 0.5s so we notice when done quickly
            for _ in range(30):
                await asyncio.sleep(0.5)
                if future.done():
                    break

        # Generation is done — retrieve result and send as SSE data event
        result: GenerateResponse = await future
        yield f"data: {result.model_dump_json()}\n\n"

    return StreamingResponse(
        sse_stream(),
        media_type="text/event-stream",
        headers={
            # Disable buffering at every layer so heartbeats flush immediately
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ComfyUI Load Balancer Worker",
        "status": "ready",
        "endpoints": {
            "POST /generate": "Generate images",
            "GET /ping": "Health check (always returns 200 OK for RunPod)",
            "GET /ready": "ComfyUI readiness check",
            "GET /stats": "Service statistics"
        }
    }


if __name__ == "__main__":
    print(f"Starting FastAPI server on port {PORT}...")
    print(f"Health check port: {PORT_HEALTH}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
