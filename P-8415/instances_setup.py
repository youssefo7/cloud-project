import json
import paramiko
import logging
import os
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
KEY_NAME = 'SQL'  # Your AWS key pair name
KEY_FILE_PATH = f'{KEY_NAME}.pem'
SSH_USERNAME = 'ubuntu'  # Default username for Ubuntu instances

# Load instance details from JSON
with open('instance_details.json', 'r') as f:
    INSTANCE_DETAILS = json.load(f)

# Function to connect to an instance via SSH
def ssh_connect(ip_address):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    logger.info(f"Connecting to {ip_address} as {SSH_USERNAME}")
    ssh.connect(ip_address, username=SSH_USERNAME, key_filename=KEY_FILE_PATH)
    return ssh

# Function to transfer a file to the instance
def transfer_file(ssh, local_path, remote_path):
    if not os.path.isfile(local_path):
        logger.error(f"Local file {local_path} does not exist.")
        raise FileNotFoundError(f"Local file {local_path} does not exist.")
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.chmod(remote_path, 0o755)  # Make script executable
    sftp.close()
    logger.info(f"Transferred {local_path} to {remote_path}")

# Function to execute a command on the instance
def execute_command(ssh, command):
    logger.info(f"Executing command: {command}")
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()  # Wait for command to complete
    output = stdout.read().decode()
    error = stderr.read().decode()
    if exit_status == 0:
        logger.info(f"Command executed successfully. Output:\n{output}")
        if error:
            logger.warning(f"Command generated warnings:\n{error}")
    else:
        logger.error(f"Command failed with exit status {exit_status}. Error:\n{error}")
    return exit_status, output, error

# Main function to set up instances
def main():
    replication_user = INSTANCE_DETAILS['replication_user']['name']
    replication_password = INSTANCE_DETAILS['replication_user']['password']
    proxy_user = INSTANCE_DETAILS['proxy_user']['name']
    proxy_password = INSTANCE_DETAILS['proxy_user']['password']
    db_name = INSTANCE_DETAILS['db_details']['db_name']
    root_password = 'root'  # Set your MySQL root password

    # Paths to local scripts
    setup_dbs_script = 'setup_dbs.sh'
    setup_replication_script = 'setup_replication.sh'
    proxy_script = 'i-proxy.py'
    gatekeeper_script = 'i-gatekeeper.py'
    trusted_host_script = 'i-trusted-host.py'
    instance_details_file = 'instance_details.json'

    # Check that all required files are present
    required_files = [
        setup_dbs_script,
        setup_replication_script,
        proxy_script,
        gatekeeper_script,
        trusted_host_script,
        instance_details_file
    ]
    for file in required_files:
        if not os.path.isfile(file):
            logger.error(f"Required file '{file}' not found in the current directory.")
            return

    # Set up the manager instance
    manager_ip = INSTANCE_DETAILS['manager']['public_ips'][0]
    manager_private_ip = INSTANCE_DETAILS['manager']['private_ips'][0]
    logger.info(f"Setting up manager at IP {manager_ip}")
    ssh_manager = ssh_connect(manager_ip)

    try:
        # Transfer instance_details.json to manager
        transfer_file(ssh_manager, instance_details_file, '/home/ubuntu/instance_details.json')

        # Transfer and execute setup_dbs.sh on manager
        transfer_file(ssh_manager, setup_dbs_script, '/home/ubuntu/setup_dbs.sh')
        command = f'sudo bash /home/ubuntu/setup_dbs.sh {root_password}'
        execute_command(ssh_manager, command)

        # Transfer and execute setup_replication.sh on manager
        transfer_file(ssh_manager, setup_replication_script, '/home/ubuntu/setup_replication.sh')
        command = f'sudo bash /home/ubuntu/setup_replication.sh manager \"\" \"\" \"\" {root_password} {replication_user} {replication_password} {proxy_user} {proxy_password}'
        execute_command(ssh_manager, command)

        # Retrieve MASTER_LOG_FILE and MASTER_LOG_POS
        # Wait a bit to ensure MySQL is fully up
        time.sleep(5)
        command = f"mysql -u root -p'{root_password}' -e 'SHOW MASTER STATUS\\G'"
        exit_status, output, error = execute_command(ssh_manager, command)
        if exit_status != 0:
            logger.error(f"Error retrieving master status from manager. Exit status {exit_status}. Error:\n{error}")
            ssh_manager.close()
            return
        else:
            logger.info("Retrieved master status from manager")
            # Parse output to get File and Position
            lines = output.strip().split('\n')
            master_status = {}
            for line in lines:
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    master_status[key.strip()] = value.strip()
            master_log_file = master_status.get('File')
            master_log_pos = master_status.get('Position')

    finally:
        ssh_manager.close()

    # Set up worker instances
    worker_ips = INSTANCE_DETAILS['worker']['public_ips']
    worker_private_ips = INSTANCE_DETAILS['worker']['private_ips']
    for i, worker_ip in enumerate(worker_ips):
        worker_private_ip = worker_private_ips[i]
        logger.info(f"Setting up worker at IP {worker_ip}")
        ssh_worker = ssh_connect(worker_ip)

        try:
            # Transfer instance_details.json to worker
            transfer_file(ssh_worker, instance_details_file, '/home/ubuntu/instance_details.json')

            # Transfer and execute setup_dbs.sh on worker
            transfer_file(ssh_worker, setup_dbs_script, '/home/ubuntu/setup_dbs.sh')
            command = f'sudo bash /home/ubuntu/setup_dbs.sh {root_password}'
            execute_command(ssh_worker, command)

            # Transfer and execute setup_replication.sh on worker
            transfer_file(ssh_worker, setup_replication_script, '/home/ubuntu/setup_replication.sh')
            command = f'sudo bash /home/ubuntu/setup_replication.sh worker {manager_private_ip} {master_log_file} {master_log_pos} {root_password} {replication_user} {replication_password} {proxy_user} {proxy_password}'
            execute_command(ssh_worker, command)

        finally:
            ssh_worker.close()

    # Set up the proxy instance
    proxy_ip = INSTANCE_DETAILS['proxy']['public_ips'][0]
    logger.info(f"Setting up proxy at IP {proxy_ip}")
    ssh_proxy = ssh_connect(proxy_ip)

    try:
        # Transfer instance_details.json to proxy
        transfer_file(ssh_proxy, instance_details_file, '/home/ubuntu/instance_details.json')

        # Install necessary packages on proxy
        logger.info("Installing necessary packages on proxy")
        commands = [
            'sudo apt-get update',
            'sudo apt-get install -y python3-pip',
            'pip3 install flask pymysql boto3 sqlparse ping3 requests'
        ]
        for cmd in commands:
            execute_command(ssh_proxy, cmd)

        # Transfer proxy.py to proxy
        transfer_file(ssh_proxy, proxy_script, '/home/ubuntu/proxy.py')

        # Start proxy.py
        logger.info("Starting proxy server")
        command = 'nohup python3 /home/ubuntu/proxy.py &> proxy.log &'
        execute_command(ssh_proxy, command)

    finally:
        ssh_proxy.close()

    # Set up the Gatekeeper instance
    gatekeeper_ip = INSTANCE_DETAILS['gatekeeper']['public_ips'][0]
    logger.info(f"Setting up Gatekeeper at IP {gatekeeper_ip}")
    ssh_gatekeeper = ssh_connect(gatekeeper_ip)

    try:
        # Transfer instance_details.json to Gatekeeper
        transfer_file(ssh_gatekeeper, instance_details_file, '/home/ubuntu/instance_details.json')

        # Install necessary packages on Gatekeeper
        logger.info("Installing necessary packages on Gatekeeper")
        commands = [
            'sudo apt-get update',
            'sudo apt-get install -y python3-pip',
            'pip3 install flask requests'
        ]
        for cmd in commands:
            execute_command(ssh_gatekeeper, cmd)

        # Transfer gatekeeper.py to Gatekeeper
        transfer_file(ssh_gatekeeper, gatekeeper_script, '/home/ubuntu/gatekeeper.py')

        # Start gatekeeper.py
        logger.info("Starting Gatekeeper server")
        command = 'nohup python3 /home/ubuntu/gatekeeper.py &> gatekeeper.log &'
        execute_command(ssh_gatekeeper, command)

    finally:
        ssh_gatekeeper.close()

    # Set up the Trusted Host instance
    trusted_host_ip = INSTANCE_DETAILS['trusted_host']['public_ips'][0]
    trusted_host_private_ip = INSTANCE_DETAILS['trusted_host']['private_ips'][0]
    gatekeeper_private_ip = INSTANCE_DETAILS['gatekeeper']['private_ips'][0]
    logger.info(f"Setting up Trusted Host at IP {trusted_host_ip}")
    ssh_trusted_host = ssh_connect(trusted_host_ip)

    try:
        # Transfer instance_details.json to Trusted Host
        transfer_file(ssh_trusted_host, instance_details_file, '/home/ubuntu/instance_details.json')

        # Install necessary packages on Trusted Host
        logger.info("Installing necessary packages on Trusted Host")
        commands = [
            'sudo apt-get update',
            'sudo apt-get install -y python3-pip ufw',
            'pip3 install flask requests'
        ]
        for cmd in commands:
            execute_command(ssh_trusted_host, cmd)

        # Transfer trusted_host.py to Trusted Host
        transfer_file(ssh_trusted_host, trusted_host_script, '/home/ubuntu/trusted_host.py')

        # Implement security measures on Trusted Host
        logger.info("Securing Trusted Host")

        # # Reset UFW to default settings
        # execute_command(ssh_trusted_host, 'echo "y" | sudo ufw reset')

        # # Deny all incoming connections by default
        # execute_command(ssh_trusted_host, 'sudo ufw default deny incoming')
        # execute_command(ssh_trusted_host, 'sudo ufw default allow outgoing')

        # Allow SSH from your IP (optional)
        # Replace 'your_public_ip' with your actual IP address if needed
        # execute_command(ssh_trusted_host, 'sudo ufw allow from your_public_ip to any port 22')

        # # Allow incoming connections on port 5000 from Gatekeeper's private IP
        # execute_command(ssh_trusted_host, f'sudo ufw allow from {gatekeeper_private_ip} to any port 5000')

        # Deny other connections to port 5000
        # Not necessary since default is deny incoming

        # # Enable UFW
        # execute_command(ssh_trusted_host, 'sudo ufw --force enable')

        # Disable SSH (optional and only if you have console access)
        # Be cautious: Disabling SSH can lock you out of the instance
        # execute_command(ssh_trusted_host, 'sudo systemctl stop ssh')
        # execute_command(ssh_trusted_host, 'sudo systemctl disable ssh')

        # Start trusted_host.py
        logger.info("Starting Trusted Host server")
        command = 'nohup python3 /home/ubuntu/trusted_host.py &> trusted_host.log &'
        execute_command(ssh_trusted_host, command)

    finally:
        ssh_trusted_host.close()

if __name__ == '__main__':
    main()
