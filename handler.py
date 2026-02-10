#!/usr/bin/env python3
"""
RunPod Serverless Handler for ComfyUI Image Generation
Processes jobs with ComfyUI and returns results
"""

import runpod
import json
import os
import sys
import base64
import time
import uuid
from typing import Dict, Any, List, Optional

# Only import requests if available
try:
    import requests
except ImportError:
    print("Warning: requests not available, installing...")
    os.system("pip install requests websocket-client")
    import requests

COMFYUI_URL = "http://127.0.0.1:8188"
COMFYUI_PATH = "/runpod-volume/ComfyUI"

print(f"Handler starting...")
print(f"Python version: {sys.version}")
print(f"Looking for ComfyUI at: {COMFYUI_PATH}")
print(f"ComfyUI exists: {os.path.exists(COMFYUI_PATH)}")

# Debug: List contents of /runpod-volume
if os.path.exists("/runpod-volume"):
    print(f"Contents of /runpod-volume: {os.listdir('/runpod-volume')}")
else:
    print("/runpod-volume does not exist - network volume not mounted")

# Global ComfyUI process
comfyui_process = None


def start_comfyui():
    """Start ComfyUI server in background if not already running"""
    global comfyui_process

    import subprocess

    # Check if ComfyUI exists
    if not os.path.exists(COMFYUI_PATH):
        raise Exception(f"ComfyUI not found at {COMFYUI_PATH}. Make sure network volume is mounted at /runpod-volume")

    main_py = f"{COMFYUI_PATH}/main.py"
    if not os.path.exists(main_py):
        raise Exception(f"ComfyUI main.py not found at {main_py}")

    # Check if already running
    try:
        response = requests.get(f"{COMFYUI_URL}/system_stats", timeout=2)
        if response.status_code == 200:
            print("ComfyUI already running")
            return
    except:
        pass

    print(f"Starting ComfyUI server from {main_py}...")
    print(f"Using Python: python3")
    print(f"Working directory: {COMFYUI_PATH}")

    # Start ComfyUI with proper python path
    env = os.environ.copy()
    env['PYTHONPATH'] = COMFYUI_PATH

    # Don't capture stdout/stderr so we can see output in logs
    print(f"Executing: python3 {main_py} --listen 127.0.0.1 --port 7860")
    comfyui_process = subprocess.Popen([
        "python3",
        main_py,
        "--listen", "127.0.0.1",
        "--port", "7860"
    ], env=env, cwd=COMFYUI_PATH)

    print(f"ComfyUI process started with PID: {comfyui_process.pid}")

    # Wait for server to be ready
    for i in range(120):
        # Check if process died
        if comfyui_process.poll() is not None:
            print(f"ERROR: ComfyUI process died with exit code {comfyui_process.returncode}")
            raise Exception(f"ComfyUI process died with exit code {comfyui_process.returncode}")

        try:
            response = requests.get(f"{COMFYUI_URL}/system_stats", timeout=2)
            if response.status_code == 200:
                print(f"ComfyUI server ready after {i} seconds")
                return
        except Exception as e:
            if i % 10 == 0:  # Log every 10 seconds
                print(f"Waiting for ComfyUI... ({i}s) - {e}")
        time.sleep(1)

    raise Exception("ComfyUI failed to start after 120 seconds")


def upload_image(image_url: str, filename: str) -> str:
    """Download image from URL and upload to ComfyUI"""
    # Download image
    response = requests.get(image_url, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Failed to download image from {image_url}")

    image_data = response.content

    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}_{filename}"

    # Upload to ComfyUI
    files = {
        'image': (unique_filename, image_data, 'image/png'),
        'type': (None, 'input'),
        'overwrite': (None, 'true')
    }

    upload_response = requests.post(
        f"{COMFYUI_URL}/upload/image",
        files=files,
        timeout=30
    )

    if upload_response.status_code != 200:
        raise Exception(f"Failed to upload image to ComfyUI: {upload_response.text}")

    result = upload_response.json()
    return result.get('name', unique_filename)


def load_workflow_template(style_id: str) -> Dict[str, Any]:
    """Load workflow template based on style"""
    is_couples = style_id == 'couples'
    filename = 'workflow_couples.json' if is_couples else 'workflow_single.json'
    filepath = f"/{filename}"  # Load from Docker image root

    with open(filepath, 'r') as f:
        return json.load(f)


def prepare_workflow(
    workflow: Dict[str, Any],
    reference_image_name: str,
    user_image1_name: str,
    user_image2_name: Optional[str],
    prompt: str,
    is_couples: bool
) -> Dict[str, Any]:
    """Prepare workflow with uploaded images and prompt"""
    workflow_str = json.dumps(workflow)

    # Escape prompt properly for JSON
    escaped_prompt = json.dumps(prompt)[1:-1]

    # Replace placeholders
    workflow_str = workflow_str.replace("PROMPT_PLACEHOLDER", escaped_prompt)

    if is_couples:
        # Couples workflow: IMAGE1=reference, IMAGE2=user1, IMAGE3=user2
        workflow_str = workflow_str.replace("IMAGE1_PLACEHOLDER", reference_image_name)
        workflow_str = workflow_str.replace("IMAGE2_PLACEHOLDER", user_image1_name)
        workflow_str = workflow_str.replace("IMAGE3_PLACEHOLDER", user_image2_name)
    else:
        # Single workflow: IMAGE1=reference, IMAGE2=user
        workflow_str = workflow_str.replace("IMAGE1_PLACEHOLDER", reference_image_name)
        workflow_str = workflow_str.replace("IMAGE2_PLACEHOLDER", user_image1_name)

    return json.loads(workflow_str)


def queue_prompt(workflow: Dict[str, Any], client_id: str) -> str:
    """Queue workflow for execution"""
    payload = {
        "prompt": workflow,
        "client_id": client_id
    }

    response = requests.post(
        f"{COMFYUI_URL}/prompt",
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"Failed to queue prompt: {response.text}")

    result = response.json()
    return result['prompt_id']


def wait_for_completion(prompt_id: str, timeout: int = 300) -> List[bytes]:
    """Wait for workflow completion and get result images"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Check history
        response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)

        if response.status_code != 200:
            time.sleep(2)
            continue

        history = response.json()

        if prompt_id not in history:
            time.sleep(2)
            continue

        prompt_history = history[prompt_id]

        # Check if completed
        if prompt_history.get('status', {}).get('completed', False):
            # Extract output images
            outputs = prompt_history.get('outputs', {})
            result_images = []

            for node_id, node_output in outputs.items():
                if 'images' in node_output:
                    for img in node_output['images']:
                        filename = img['filename']
                        subfolder = img.get('subfolder', '')
                        img_type = img.get('type', 'output')

                        # Download image
                        params = {
                            'filename': filename,
                            'subfolder': subfolder,
                            'type': img_type
                        }
                        img_response = requests.get(
                            f"{COMFYUI_URL}/view",
                            params=params,
                            timeout=30
                        )

                        if img_response.status_code == 200:
                            result_images.append(img_response.content)

            return result_images

        # Check for errors
        if 'status' in prompt_history and 'status_str' in prompt_history['status']:
            status_str = prompt_history['status']['status_str']
            if 'error' in status_str.lower():
                raise Exception(f"ComfyUI workflow failed: {status_str}")

        time.sleep(2)

    raise Exception(f"Workflow timed out after {timeout} seconds")


def handler(event):
    """
    RunPod handler function

    Expected input:
    {
        "jobId": "uuid",
        "styleId": "single" or "couples",
        "userImage1Url": "https://...",
        "userImage2Url": "https://..." (optional for couples),
        "referenceImageUrl": "https://...",
        "prompt": "style prompt text"
    }

    Returns:
    {
        "status": "completed",
        "jobId": "uuid",
        "images": ["base64_encoded_image1", ...]
    }
    """
    # Extract input first so it's available in error handler
    input_data = event.get("input", {})

    try:
        # Wait for ComfyUI to be ready (it's started by the base image)
        print("Waiting for ComfyUI to be ready...")
        for i in range(60):
            try:
                response = requests.get(f"{COMFYUI_URL}/system_stats", timeout=2)
                if response.status_code == 200:
                    print(f"ComfyUI is ready after {i} seconds")
                    break
            except:
                if i % 10 == 0:
                    print(f"Still waiting for ComfyUI... ({i}s)")
                time.sleep(1)
        else:
            raise Exception("ComfyUI not ready after 60 seconds")

        job_id = input_data.get("jobId")
        style_id = input_data.get("styleId", "single")
        user_image1_url = input_data.get("userImage1Url")
        user_image2_url = input_data.get("userImage2Url")
        reference_image_url = input_data.get("referenceImageUrl")
        prompt = input_data.get("prompt", "")

        # Validate inputs
        if not job_id or not user_image1_url or not reference_image_url:
            return {
                "status": "failed",
                "error": "Missing required fields: jobId, userImage1Url, referenceImageUrl"
            }

        is_couples = style_id == 'couples'
        if is_couples and not user_image2_url:
            return {
                "status": "failed",
                "error": "Missing userImage2Url for couples style"
            }

        print(f"Processing job {job_id} with style {style_id}")

        # Upload images to ComfyUI
        print("Uploading reference image...")
        reference_image_name = upload_image(reference_image_url, "reference.png")

        print("Uploading user image 1...")
        user_image1_name = upload_image(user_image1_url, "user1.png")

        user_image2_name = None
        if user_image2_url:
            print("Uploading user image 2...")
            user_image2_name = upload_image(user_image2_url, "user2.png")

        # Load and prepare workflow
        print("Loading workflow template...")
        workflow = load_workflow_template(style_id)

        print("Preparing workflow...")
        workflow = prepare_workflow(
            workflow,
            reference_image_name,
            user_image1_name,
            user_image2_name,
            prompt,
            is_couples
        )

        # Queue prompt
        client_id = str(uuid.uuid4())
        print(f"Queueing prompt with client_id {client_id}...")
        prompt_id = queue_prompt(workflow, client_id)

        print(f"Prompt queued with ID {prompt_id}, waiting for completion...")

        # Wait for results
        result_images = wait_for_completion(prompt_id, timeout=900)

        print(f"Workflow completed, got {len(result_images)} images")

        # Encode images as base64
        encoded_images = []
        for img_data in result_images:
            encoded = base64.b64encode(img_data).decode('utf-8')
            encoded_images.append(encoded)

        return {
            "status": "completed",
            "jobId": job_id,
            "images": encoded_images,
            "message": f"Generated {len(encoded_images)} images successfully"
        }

    except Exception as e:
        print(f"Error processing job: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "status": "failed",
            "jobId": input_data.get("jobId", "unknown"),
            "error": str(e)
        }


# Don't start ComfyUI during init - wait for first request to avoid timeout
print("Handler initialized, waiting for jobs...")

if __name__ == "__main__":
    print("Starting RunPod serverless handler...")
    runpod.serverless.start({"handler": handler})
