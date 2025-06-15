from io import BytesIO
import IPython
import json
import os
from PIL import Image
import requests
import time

STABILITY_KEY = os.getenv("STABILITY_API_KEY")


def send_generation_request(host, params, files=None):
    headers = {"Accept": "image/*", "Authorization": f"Bearer {STABILITY_KEY}"}

    if files is None:
        files = {}

    # Encode parameters
    image = params.pop("image", None)
    mask = params.pop("mask", None)
    if image is not None and image != "":
        files["image"] = open(image, "rb")
    if mask is not None and mask != "":
        files["mask"] = open(mask, "rb")
    if len(files) == 0:
        files["none"] = ""

    # Send request
    print(f"Sending REST request to {host}...")
    response = requests.post(host, headers=headers, files=files, data=params)
    if not response.ok:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    return response


def send_async_generation_request(host, params, files=None):
    headers = {"Accept": "application/json", "Authorization": f"Bearer {STABILITY_KEY}"}

    if files is None:
        files = {}

    # Encode parameters
    image = params.pop("image", None)
    mask = params.pop("mask", None)
    if image is not None and image != "":
        files["image"] = open(image, "rb")
    if mask is not None and mask != "":
        files["mask"] = open(mask, "rb")
    if len(files) == 0:
        files["none"] = ""

    # Send request
    print(f"Sending REST request to {host}...")
    response = requests.post(host, headers=headers, files=files, data=params)
    if not response.ok:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    # Process async response
    response_dict = json.loads(response.text)
    generation_id = response_dict.get("id", None)
    assert generation_id is not None, "Expected id in response"

    # Loop until result or timeout
    timeout = int(os.getenv("WORKER_TIMEOUT", 500))
    start = time.time()
    status_code = 202
    while status_code == 202:
        print(
            f"Polling results at https://api.stability.ai/v2beta/results/{generation_id}"
        )
        response = requests.get(
            f"https://api.stability.ai/v2beta/results/{generation_id}",
            headers={**headers, "Accept": "*/*"},
        )

        if not response.ok:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        status_code = response.status_code
        time.sleep(10)
        if time.time() - start > timeout:
            raise Exception(f"Timeout after {timeout} seconds")

    return response


# company_input ='''
# Kukumber is your child's AI math companion designed to make kids aged 5-9 love math, with over 1,000 playful
# lessons, a friendly talking AI mascot, and zero ads—helping children build learning habits,
# boost confidence, and make real progress in just 20 minutes a day, all developed in collaboration
# with 100+ parents and teachers for a frustration-free, fun learning experience.
# '''

company_input = """
"""


prompt = f"An eye-catching, cinematic advertisement visual for the company described below: {company_input}"

negative_prompt = "blurry, low-res, text artifacts, distorted faces, overexposed, underexposed, extra limbs, watermark, low detail"
aspect_ratio = "16:9"
style_preset = "enhance"
seed = 0
output_format = "jpeg"

host = f"https://api.stability.ai/v2beta/stable-image/generate/core"

params = {
    "prompt": prompt,
    "negative_prompt": negative_prompt,
    "aspect_ratio": aspect_ratio,
    "seed": seed,
    "output_format": output_format,
}

if style_preset != "None":
    params["style_preset"] = style_preset

response = send_generation_request(host, params)
output_image = response.content
finish_reason = response.headers.get("finish-reason")
seed = response.headers.get("seed")

if finish_reason == "CONTENT_FILTERED":
    raise Warning("Generation failed NSFW classifier")

generated = f"generated_{seed}.{output_format}"

with open(generated, "wb") as f:
    f.write(output_image)

print(f"Saved image {generated}")
