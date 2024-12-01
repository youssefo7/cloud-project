from flask import Flask, request, jsonify
import requests
import json

app = Flask(__name__)

# Proxy Configuration
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

# Proxy Configuration
PROXY_PRIVATE_IP = INSTANCE_DETAILS['proxy']['private_ips'][0]
PROXY_URL = f"http://{PROXY_PRIVATE_IP}:5000"
@app.route('/process', methods=['POST'])
def process_request():
    data = request.get_json()
    query = data.get('query', '').strip()

    # Handle SET_MODE commands
    if query.startswith("SET_MODE"):
        mode = query.split()[-1]
        try:
            response = requests.post(f"{PROXY_URL}/set_mode/{mode}")
            return jsonify(response.json()), response.status_code
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Forward SQL queries to the Proxy
    try:
        response = requests.post(f"{PROXY_URL}/query", json={"query": query})
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
