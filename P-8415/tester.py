import boto3
import paramiko
import os

# AWS configuration
REGION = 'us-east-1'  # Replace with your AWS region
INSTANCE_ID = 'i-03d45d586c12e2658'  # Replace with your instance ID or set to None if using IP

# Replace with the path to your SSH private key file
KEY_FILE_PATH = 'SQL.pem'

# Replace with the username for your instance (e.g., 'ubuntu' for Ubuntu AMIs)
USERNAME = 'ubuntu'

# Replace with the path to the script you want to deploy
LOCAL_SCRIPT_PATH = 'setup_proxy.sh'

# Remote path where the script will be uploaded
REMOTE_SCRIPT_PATH = f'/home/{USERNAME}/{os.path.basename(LOCAL_SCRIPT_PATH)}'

def get_instance_public_ip(instance_id, region):
    ec2 = boto3.resource('ec2', region_name=region)
    instance = ec2.Instance(instance_id)
    instance.load()
    return instance.public_ip_address

def deploy_and_execute_script(instance_ip, username, key_file_path, local_script_path, remote_script_path):
    try:
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(instance_ip, username=username, key_filename=key_file_path)
        print(f"Connected to {instance_ip}")
        
        # Send the script
        sftp = ssh.open_sftp()
        sftp.put(local_script_path, remote_script_path)
        sftp.close()
        print(f"Uploaded script to {remote_script_path}")
        
        # Make the script executable
        ssh.exec_command(f'chmod +x {remote_script_path}')
        print(f"Set execute permissions on {remote_script_path}")
        
        # Execute the script
        stdin, stdout, stderr = ssh.exec_command(f'sudo {remote_script_path}')
        print(f"Executing script {remote_script_path} on {instance_ip}")
        
        # Read the output and errors
        stdout_text = stdout.read().decode()
        stderr_text = stderr.read().decode()
        
        print("Script output:")
        print(stdout_text)
        if stderr_text:
            print("Script errors:")
            print(stderr_text)
        
        # Close SSH connection
        ssh.close()
        print(f"Disconnected from {instance_ip}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    # Determine the instance IP address
    if INSTANCE_ID:
        # Get the instance's public IP address using its ID
        instance_ip = get_instance_public_ip(INSTANCE_ID, REGION)
        print(f"Instance {INSTANCE_ID} has public IP: {instance_ip}")
    else:
        raise ValueError("Either INSTANCE_ID or INSTANCE_IP must be set.")
    
    deploy_and_execute_script(
        instance_ip,
        USERNAME,
        KEY_FILE_PATH,
        LOCAL_SCRIPT_PATH,
        REMOTE_SCRIPT_PATH
    )
