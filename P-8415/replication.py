import paramiko

# SSH Configuration
KEY_FILE_PATH = 'SQL.pem'  # Path to your SSH private key
USERNAME = 'ubuntu'  # Instance username (e.g., 'ubuntu' for Ubuntu AMIs)

# Paths
LOCAL_SCRIPT_PATH = 'replica-setup.sh'  # Path to the local script
REMOTE_SCRIPT_PATH = '/tmp/replication_setup.sh'  # Path where the script will be uploaded

# Instance IPs
MANAGER_PUBLIC_IP = "3.91.215.132"  # Public IP of the manager instance
MANAGER_PRIVATE_IP = "172.31.23.200"  # Private IP of the manager instance
WORKER_IPS = ["52.201.51.167", "54.221.53.102"]  # Public IPs of worker instances

# Roles
MANAGER_ROLE = "manager"
WORKER_ROLE = "worker"

def get_master_status():
    """Retrieve the master log file and position from the manager."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(MANAGER_PUBLIC_IP, username=USERNAME, key_filename=KEY_FILE_PATH)
    stdin, stdout, stderr = ssh.exec_command(r'mysql -u root -pYOUR_ROOT_PASSWORD -e "SHOW MASTER STATUS\G"')
    output = stdout.read().decode()
    stderr_text = stderr.read().decode()
    ssh.close()
    
    if stderr_text and 'Warning' not in stderr_text:
        print(f"Errors from master:\n{stderr_text}")
        return None, None

    master_log_file = ''
    master_log_pos = ''
    for line in output.splitlines():
        if "File:" in line:
            master_log_file = line.split(":")[1].strip()
        elif "Position:" in line:
            master_log_pos = line.split(":")[1].strip()
    return master_log_file, master_log_pos

def deploy_and_execute(instance_ip, role, username, key_file_path, local_script_path, remote_script_path, extra_args=""):
    """Deploy and execute a replication setup script on a remote instance."""
    try:
        # Create an SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(instance_ip, username=username, key_filename=key_file_path)
        print(f"Connected to {instance_ip}")

        # Transfer the script to the remote instance
        sftp = ssh.open_sftp()
        sftp.put(local_script_path, remote_script_path)
        sftp.close()
        print(f"Uploaded script to {remote_script_path}")

        # Make the script executable
        ssh.exec_command(f"chmod +x {remote_script_path}")
        print(f"Set execute permissions for {remote_script_path}")

        # Execute the script with the specified role and extra arguments
        command = f"sudo {remote_script_path} {role} {extra_args}"
        stdin, stdout, stderr = ssh.exec_command(command)
        print(f"Executing script on {instance_ip} with role '{role}' and args '{extra_args}'")

        # Capture output and errors
        stdout_text = stdout.read().decode()
        stderr_text = stderr.read().decode()

        print(f"Output from {instance_ip} ({role}):\n{stdout_text}")
        if stderr_text:
            print(f"Errors from {instance_ip} ({role}):\n{stderr_text}")

        # Close the SSH connection
        ssh.close()
        print(f"Disconnected from {instance_ip}")
    except Exception as e:
        print(f"Error on {instance_ip}: {e}")


def main():
    # Deploy and execute the script on the manager
    print("Configuring Manager Node...")
    deploy_and_execute(MANAGER_PUBLIC_IP, MANAGER_ROLE, USERNAME, KEY_FILE_PATH, LOCAL_SCRIPT_PATH, REMOTE_SCRIPT_PATH)

    # Get the master log file and position
    print("Retrieving master status...")
    master_log_file, master_log_pos = get_master_status()
    if not master_log_file or not master_log_pos:
        print("Failed to retrieve master log file and position.")
        return

    print(f"Master Log File: {master_log_file}")
    print(f"Master Log Position: {master_log_pos}")

    # Deploy and execute the script on each worker
    for worker_ip in WORKER_IPS:
        print(f"Configuring Worker Node at {worker_ip}...")
        extra_args = f"{MANAGER_PRIVATE_IP} {master_log_file} {master_log_pos}"
        deploy_and_execute(worker_ip, WORKER_ROLE, USERNAME, KEY_FILE_PATH, LOCAL_SCRIPT_PATH, REMOTE_SCRIPT_PATH, extra_args)

if __name__ == "__main__":
    main()
