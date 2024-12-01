from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Proxy Configuration
PROXY_URL = "http://172.31.23.96:3306"  # Replace with Proxy private IP

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
