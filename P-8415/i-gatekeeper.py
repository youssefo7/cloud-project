from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# Load instance details from local file
CONFIG_FILE_PATH = "/home/ubuntu/instance_details.json"
INSTANCE_DETAILS = {}

def load_instance_details():
    global INSTANCE_DETAILS
    try:
        with open(CONFIG_FILE_PATH, "r") as f:
            INSTANCE_DETAILS = json.load(f)
        app.logger.info("Loaded instance details from local configuration file.")
    except Exception as e:
        app.logger.error(f"Failed to load instance details: {e}")
        raise

load_instance_details()

# Trusted Host Configuration
TRUSTED_HOST_PRIVATE_IP = INSTANCE_DETAILS['trusted_host']['private_ips'][0]
TRUSTED_HOST_URL = f"http://{TRUSTED_HOST_PRIVATE_IP}:5000"

# A simple filter for allowed operations
ALLOWED_OPERATIONS = ["SELECT", "INSERT", "UPDATE", "DELETE", "SET_MODE"]

@app.route('/filter', methods=['POST'])
def filter_request():
    data = request.get_json()

    # Validate request data
    if not data or 'query' not in data:
        return jsonify({"error": "Invalid request. Query missing."}), 400

    query = data['query'].strip()
    normalized_query = query.upper()  # Normalize query to uppercase for validation

    # Check if query starts with an allowed operation
    if not any(normalized_query.startswith(op) for op in ALLOWED_OPERATIONS):
        app.logger.warning(f"Disallowed operation detected: {query}")
        return jsonify({"error": f"Operation not allowed: {query}"}), 403

    # Forward validated query to Trusted Host
    try:
        response = requests.post(f"{TRUSTED_HOST_URL}/process", json=data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        app.logger.error(f"Error forwarding to Trusted Host: {e}")
        return jsonify({"error": f"Error forwarding to Trusted Host: {e}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
