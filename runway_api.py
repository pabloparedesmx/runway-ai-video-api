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
    xano_response = requests.post(f"{XANO_API_URL}/video_requests", json={
        "image_url": image_url,
        "prompt": prompt,
        "status": "pending"
    })

    if xano_response.status_code != 200:
        return jsonify({"error": "Failed to create request in Xano"}), 500

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

    response = requests.post(RUNWAY_API_URL, json=payload, headers=headers)

    if response.status_code == 200:
        result = response.json()
        
        # Update Xano with the result
        requests.patch(f"{XANO_API_URL}/video_requests/{request_id}", json={
            "status": "completed",
            "result_url": result.get('output', {}).get('video', '')
        })

        return jsonify(result)
    else:
        # Update Xano with error status
        requests.patch(f"{XANO_API_URL}/video_requests/{request_id}", json={
            "status": "failed"
        })
        return jsonify({"error": "Failed to generate video", "details": response.text}), response.status_code

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify(error=str(e)), 405

if __name__ == '__main__':
    app.run(debug=True)
