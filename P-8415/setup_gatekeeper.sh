#!/bin/bash

# Update package lists
sudo apt-get update

# Install Nginx
sudo apt-get install -y nginx

# Install Python and necessary packages
sudo apt-get install -y python3 python3-pip
pip3 install flask requests

# Configure Nginx to reverse proxy to Flask app
sudo tee /etc/nginx/sites-available/gatekeeper <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:5000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# Enable the site and restart Nginx
sudo ln -s /etc/nginx/sites-available/gatekeeper /etc/nginx/sites-enabled/
sudo systemctl restart nginx

# Create the Flask application
mkdir ~/gatekeeper_app
cd ~/gatekeeper_app

cat > app.py <<EOF
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TRUSTED_HOST_URL = 'http://TRUSTED_HOST_IP:5000/'  # Replace with Trusted Host IP

@app.route('/', methods=['GET', 'POST'])
def handle_request():
    # Validate input (implement validation logic)
    data = request.get_json() or {}
    # Perform input validation here

    # Forward validated request to Trusted Host
    response = requests.post(TRUSTED_HOST_URL, json=data)
    return response.content, response.status_code

if __name__ == '__main__':
    app.run(debug=False)
EOF

# Replace 'TRUSTED_HOST_IP' with the private IP address of the Trusted Host

# Run the Flask application (you might want to run this as a service)
nohup python3 app.py &

echo "Gatekeeper setup complete."
