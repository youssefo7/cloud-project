#!/bin/bash

# Assign arguments to variables
YOUR_IP="$1"
GATEKEEPER_IP="$2"
PROXY_IP="$3"

# Update package lists and upgrade packages
sudo apt-get update
sudo apt-get upgrade -y

# Install necessary packages
sudo apt-get install -y python3 python3-pip ufw

# Harden the system
# Disable root SSH login
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Disable unnecessary services (adjust as needed)
sudo systemctl stop apache2
sudo systemctl disable apache2

# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH from your IP
sudo ufw allow from "$YOUR_IP" to any port 22

# Allow connections from Gatekeeper only
sudo ufw allow from "$GATEKEEPER_IP" to any port 5000  # Assuming the app listens on port 5000

# Enable UFW
echo "y" | sudo ufw enable

# Create the application to process requests
mkdir -p ~/trusted_host_app
cd ~/trusted_host_app

sudo pip3 install flask mysql-connector-python

cat > app.py <<EOF
from flask import Flask, request, jsonify
import mysql.connector

app = Flask(__name__)

PROXY_HOST = '$PROXY_IP'  # Replace with Proxy server IP
PROXY_PORT = 6033  # Default ProxySQL port

@app.route('/', methods=['POST'])
def handle_request():
    data = request.get_json() or {}
    # Process the data as needed

    # Decide if it's a read or write operation
    query = data.get('query', '')
    try:
        conn = mysql.connector.connect(
            host=PROXY_HOST,
            port=PROXY_PORT,
            user='root',
            password='',  # No password
            database='sakila'
        )
        cursor = conn.cursor()
        cursor.execute(query)
        if cursor.with_rows:
            result = cursor.fetchall()
            return jsonify(result)
        else:
            conn.commit()
            return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# Run the Flask application (consider running as a service)
nohup python3 app.py &

echo "Trusted Host setup complete."
