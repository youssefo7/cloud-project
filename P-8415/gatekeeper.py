from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Trusted Host Configuration
TRUSTED_HOST_URL = "http://172.31.21.4:5000"  # Replace with Trusted Host private IP

# A simple filter for allowed operations
ALLOWED_OPERATIONS = ["SELECT", "INSERT", "UPDATE", "DELETE", "USE", "SET_MODE", "CREATE", "DROP"]

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
        return jsonify({"error": f"Operation not allowed: {query}"}), 403

    # Forward validated query to Trusted Host
    try:
        response = requests.post(f"{TRUSTED_HOST_URL}/process", json=data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": f"Error forwarding to Trusted Host: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
