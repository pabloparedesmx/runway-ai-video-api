import os
import logging
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

RUNWAY_API_KEY = os.environ.get('RUNWAY_API_KEY')
RUNWAY_API_URL = "https://api.runwayml.com/v1/inference"
XANO_API_URL = os.environ.get('XANO_API_URL')

@app.route('/generate-video', methods=['POST'])
def generate_video():
    data = request.json
    image_url = data.get('image_url')
    prompt = data.get('prompt')

    if not image_url or not prompt:
        return jsonify({"error": "Missing image_url or prompt"}), 400

    logging.debug(f"Received request: {data}")

    # Create a request in Xano
    try:
        xano_payload = {
            "image_url": image_url,
            "prompt": prompt,
            "status": "pending"
        }
        logging.debug(f"Sending to Xano: {xano_payload}")
        xano_response = requests.post(f"{XANO_API_URL}/video_requests", json=xano_payload)
        logging.debug(f"Xano response status: {xano_response.status_code}")
        logging.debug(f"Xano response content: {xano_response.text}")
        xano_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to create request in Xano: {str(e)}")
        return jsonify({
            "error": "Failed to create request in Xano",
            "details": str(e),
            "xano_url": XANO_API_URL
        }), 500

    xano_data = xano_response.json()
    if not xano_data:
        logging.error("Xano returned empty data")
        return jsonify({"error": "Xano returned empty data"}), 500

    request_id = xano_data[0].get('id')
    if not request_id:
        logging.error("No request ID returned from Xano")
        return jsonify({"error": "No request ID returned from Xano"}), 500

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
        logging.debug(f"Sending to Runway AI: {payload}")
        response = requests.post(RUNWAY_API_URL, json=payload, headers=headers)
        logging.debug(f"Runway AI response status: {response.status_code}")
        logging.debug(f"Runway AI response content: {response.text}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to generate video: {str(e)}")
        # Update Xano with error status
        try:
            requests.patch(f"{XANO_API_URL}/video_requests/{request_id}", json={"status": "failed"})
        except:
            logging.error("Failed to update Xano with error status")
        return jsonify({"error": "Failed to generate video", "details": str(e)}), 500

    result = response.json()
    
    # Update Xano with the result
    try:
        update_payload = {
            "status": "completed",
            "result_url": result.get('output', {}).get('video', '')
        }
        logging.debug(f"Updating Xano with: {update_payload}")
        update_response = requests.patch(f"{XANO_API_URL}/video_requests/{request_id}", json=update_payload)
        logging.debug(f"Xano update response status: {update_response.status_code}")
        logging.debug(f"Xano update response content: {update_response.text}")
        update_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to update Xano with result: {str(e)}")
        return jsonify({"error": "Failed to update Xano with result", "details": str(e)}), 500

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
