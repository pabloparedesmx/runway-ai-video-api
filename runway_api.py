import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

RUNWAY_API_KEY = os.environ.get('RUNWAY_API_KEY')
RUNWAY_API_URL = "https://api.runwayml.com/v1/inference"
XANO_API_URL = os.environ.get('XANO_API_URL')

@app.route('/', methods=['GET', 'POST'])
def hello():
    if request.method == 'GET':
        return "Hello, World! Runway AI Video Generation API is running. Use POST /generate-video to generate videos."
    elif request.method == 'POST':
        return jsonify({
            "message": "This is the root endpoint. To generate videos, use POST /generate-video",
            "received_data": request.json
        })

@app.route('/generate-video', methods=['POST'])
def generate_video():
    data = request.json
    image_url = data.get('image_url')
    prompt = data.get('prompt')

    if not image_url or not prompt:
        return jsonify({"error": "Missing image_url or prompt"}), 400

    # Create a request in Xano
    try:
        xano_response = requests.post(f"{XANO_API_URL}/video_requests", json={
            "image_url": image_url,
            "prompt": prompt,
            "status": "pending"
        })
        xano_response.raise_for_status()  # This will raise an exception for 4xx and 5xx status codes
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "Failed to create request in Xano",
            "details": str(e),
            "xano_url": XANO_API_URL
        }), 500

    xano_data = xano_response.json()
    request_id = xano_data['id']

    # Call Runway AI API
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "input": {
            "image": image_url,
            "prompt": prompt
        }
    }

    try:
        response = requests.post(RUNWAY_API_URL, json=payload, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Update Xano with error status
        requests.patch(f"{XANO_API_URL}/video_requests/{request_id}", json={
            "status": "failed"
        })
        return jsonify({"error": "Failed to generate video", "details": str(e)}), 500

    result = response.json()
    
    # Update Xano with the result
    try:
        requests.patch(f"{XANO_API_URL}/video_requests/{request_id}", json={
            "status": "completed",
            "result_url": result.get('output', {}).get('video', '')
        }).raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to update Xano with result", "details": str(e)}), 500

    return jsonify(result)

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify(error=str(e)), 405

if __name__ == '__main__':
    app.run(debug=True)
