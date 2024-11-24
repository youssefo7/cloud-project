import boto3
import time
import os
import paramiko
import logging
import requests
import argparse
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS resources
ec2 = boto3.resource('ec2')
ec2_client = boto3.client('ec2')

# Constants
KEY_NAME = 'SQL'  # Update with your key pair name
SECURITY_GROUP_NAME = 'SQL'  # Update with your security group name
INSTANCE_TAG_PREFIX = 'MySQLCluster'  # Tag prefix for your instances
KEY_FILE_PATH = f'{KEY_NAME}.pem'
AMI_ID = 'ami-005fc0f236362e99f'  # Replace with the correct AMI ID for your region

# Function to parse command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description='AWS EC2 Deployment Script')
    parser.add_argument('--create-instances', action='store_true', help='Create new instances')
    parser.add_argument('--deploy-scripts', action='store_true', help='Deploy scripts to instances')
    parser.add_argument('--setup-aws-resources', action='store_true', help='Setup AWS resources (key pair, security group)')
    return parser.parse_args()

# Function to check if a key pair exists
def key_pair_exists(key_name):
    try:
        ec2_client.describe_key_pairs(KeyNames=[key_name])
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidKeyPair.NotFound':
            return False
        else:
            logger.error(f"Error checking key pair: {e}")
            raise

# Function to create a key pair
def create_key_pair(key_name):
    try:
        key_pair = ec2_client.create_key_pair(KeyName=key_name)
        private_key = key_pair['KeyMaterial']
        # Save the private key to a .pem file
        with os.fdopen(os.open(f'{key_name}.pem', os.O_WRONLY | os.O_CREAT, 0o400), 'w') as handle:
            handle.write(private_key)
        logger.info(f"Key pair '{key_name}' created and saved as {key_name}.pem")
    except ClientError as e:
        logger.error(f"Error creating key pair: {e}")
        raise

# Function to check if a security group exists
def security_group_exists(security_group_name):
    try:
        ec2_client.describe_security_groups(GroupNames=[security_group_name])
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidGroup.NotFound':
            return False
        else:
            logger.error(f"Error checking security group: {e}")
            raise

# Function to create a security group
def create_security_group(security_group_name):
    try:
        response = ec2_client.create_security_group(
            GroupName=security_group_name,
            Description="Security group for MySQL cluster"
        )
        security_group_id = response['GroupId']
        logger.info(f"Security group '{security_group_name}' created with ID: {security_group_id}")
        return security_group_id
    except ClientError as e:
        logger.error(f"Error creating security group: {e}")
        raise

# Function to set ingress rules for the security group
def authorize_security_group_ingress(security_group_id):
    try:
        # Define required ports
        required_ports = [
            {'FromPort': 22, 'ToPort': 22, 'IpProtocol': 'tcp'},          # SSH
            {'FromPort': 3306, 'ToPort': 3306, 'IpProtocol': 'tcp'},      # MySQL
            # Add other ports if necessary
        ]
        ip_permissions = []
        for port in required_ports:
            ip_permissions.append({
                'IpProtocol': port['IpProtocol'],
                'FromPort': port['FromPort'],
                'ToPort': port['ToPort'],
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
            })
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=ip_permissions
        )
        logger.info(f"Ingress rules set for security group ID: {security_group_id}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidPermission.Duplicate':
            logger.info("Ingress rules already set.")
        else:
            logger.error(f"Error setting ingress rules: {e}")
            raise

# Function to launch instances for a specific role
def launch_instances_for_role(key_name, security_group_id, instance_type, instance_count, instance_tags):
    try:
        instances = ec2.create_instances(
            ImageId=AMI_ID,
            MinCount=instance_count,
            MaxCount=instance_count,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': instance_tags
                }
            ]
        )
        instance_ids = [instance.id for instance in instances]
        logger.info(f"Launched instances: {instance_ids}")
        return instance_ids
    except ClientError as e:
        logger.error(f"Error launching instances: {e}")
        raise

# Function to wait for instances to initialize
def wait_for_instances_to_initialize(instance_ids):
    logger.info("Waiting for instances to initialize...")
    instances = ec2.instances.filter(InstanceIds=instance_ids)
    for instance in instances:
        instance.wait_until_running()
        instance.reload()
    logger.info("Instances are now running.")

# Function to retrieve instances by role
def get_instances_by_role(role):
    instances = ec2.instances.filter(
        Filters=[
            {'Name': 'tag:Role', 'Values': [role]},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )
    return instances

# Function to retrieve instance IPs by role
def retrieve_instance_ips_by_role():
    roles = ['manager', 'worker', 'proxy', 'gatekeeper', 'trusted_host']
    instance_ips = {}
    for role in roles:
        instances = get_instances_by_role(role)
        public_ips = []
        private_ips = []
        for instance in instances:
            instance.load()
            public_ips.append(instance.public_ip_address)
            private_ips.append(instance.private_ip_address)
        instance_ips[role] = {
            'public_ips': public_ips,
            'private_ips': private_ips
        }
    return instance_ips

# Function to deploy and execute a script on an instance
def deploy_and_execute_script(ip, key_file_path, script_path, args=None):
    logger.info(f"Deploying script {script_path} to instance at {ip}")
    try:
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username='ubuntu', key_filename=key_file_path)
        # Send the setup script
        sftp = ssh.open_sftp()
        remote_script_path = f'/home/ubuntu/{os.path.basename(script_path)}'
        sftp.put(script_path, remote_script_path)
        sftp.close()
        # Make the script executable
        ssh.exec_command(f'chmod +x {remote_script_path}')
        # Prepare command
        command = f'sudo {remote_script_path}'
        if args:
            command += ' ' + ' '.join(args)
        # Run the script
        logger.info(f"Executing command on {ip}: {command}")
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        # Optionally, log output
        logger.info(stdout.read().decode())
        logger.error(stderr.read().decode())
        ssh.close()
    except Exception as e:
        logger.error(f"Error setting up instance at {ip}: {e}")

# Function to setup AWS resources
def setup_aws_resources(key_name, security_group_name):
    # Check and create key pair
    logger.info("Checking key pair...")
    if not key_pair_exists(key_name):
        create_key_pair(key_name)
    else:
        logger.info(f"Key pair '{key_name}' already exists.")

    # Check and create security group
    logger.info("Setting up security group...")
    if not security_group_exists(security_group_name):
        security_group_id = create_security_group(security_group_name)
        authorize_security_group_ingress(security_group_id)
    else:
        response = ec2_client.describe_security_groups(GroupNames=[security_group_name])
        security_group_id = response['SecurityGroups'][0]['GroupId']
        logger.info(f"Using existing security group '{security_group_name}' with ID: {security_group_id}")
    return security_group_id

# Main function
if __name__ == "__main__":
    args = parse_arguments()

    # Setup AWS resources if requested
    if args.setup_aws_resources or args.create_instances:
        security_group_id = setup_aws_resources(KEY_NAME, SECURITY_GROUP_NAME)
    else:
        response = ec2_client.describe_security_groups(GroupNames=[SECURITY_GROUP_NAME])
        security_group_id = response['SecurityGroups'][0]['GroupId']

    instance_ids = {}

    # Create instances if requested
    if args.create_instances:
        # Launch instances for each role
        instance_ids['manager'] = launch_instances_for_role(
            KEY_NAME, security_group_id, 't2.micro', 1,
            [{'Key': 'Name', 'Value': f'{INSTANCE_TAG_PREFIX}-MySQL-Manager'}, {'Key': 'Role', 'Value': 'manager'}]
        )
        instance_ids['worker'] = launch_instances_for_role(
            KEY_NAME, security_group_id, 't2.micro', 2,
            [{'Key': 'Name', 'Value': f'{INSTANCE_TAG_PREFIX}-MySQL-Worker'}, {'Key': 'Role', 'Value': 'worker'}]
        )
        instance_ids['proxy'] = launch_instances_for_role(
            KEY_NAME, security_group_id, 't2.large', 1,
            [{'Key': 'Name', 'Value': 'Proxy-Server'}, {'Key': 'Role', 'Value': 'proxy'}]
        )
        instance_ids['gatekeeper'] = launch_instances_for_role(
            KEY_NAME, security_group_id, 't2.large', 1,
            [{'Key': 'Name', 'Value': 'Gatekeeper'}, {'Key': 'Role', 'Value': 'gatekeeper'}]
        )
        instance_ids['trusted_host'] = launch_instances_for_role(
            KEY_NAME, security_group_id, 't2.large', 1,
            [{'Key': 'Name', 'Value': 'Trusted-Host'}, {'Key': 'Role', 'Value': 'trusted_host'}]
        )
        # Combine all instance IDs
        all_instance_ids = []
        for ids in instance_ids.values():
            all_instance_ids.extend(ids)
        # Wait for instances to initialize
        wait_for_instances_to_initialize(all_instance_ids)
    else:
        logger.info("Using existing instances.")

    # Deploy scripts if requested
    if args.deploy_scripts:
        # Retrieve instance IPs
        instance_ips = retrieve_instance_ips_by_role()

        # Retrieve your public IP
        logger.info("Retrieving your public IP...")
        try:
            response = requests.get('https://api.ipify.org?format=json')
            YOUR_IP = response.json()['ip']
            logger.info(f"Your public IP: {YOUR_IP}")
        except Exception as e:
            logger.error(f"Could not retrieve your public IP: {e}")
            YOUR_IP = 'YOUR_IP'  # Replace with your actual IP if needed

        # Deploy scripts to instances
        # For proxy
        proxy_public_ip = instance_ips['proxy']['public_ips'][0]
        manager_private_ip = instance_ips['manager']['private_ips'][0]
        worker_private_ips = instance_ips['worker']['private_ips']
        worker_ips_str = ','.join(worker_private_ips)
        deploy_and_execute_script(proxy_public_ip, KEY_FILE_PATH, 'setup_proxy.sh', args=[manager_private_ip, worker_ips_str])

        # For trusted host
        trusted_host_public_ip = instance_ips['trusted_host']['public_ips'][0]
        gatekeeper_private_ip = instance_ips['gatekeeper']['private_ips'][0]
        proxy_private_ip = instance_ips['proxy']['private_ips'][0]
        deploy_and_execute_script(trusted_host_public_ip, KEY_FILE_PATH, 'setup_trusted_host.sh', args=[YOUR_IP, gatekeeper_private_ip, proxy_private_ip])

        # For other instances
        role_to_script = {
            'manager': 'setup_minis.sh',
            'worker': 'setup_minis.sh',
            'gatekeeper': 'setup_gatekeeper.sh'
        }
        for role in ['manager', 'worker', 'gatekeeper']:
            ips = instance_ips[role]['public_ips']
            script = role_to_script[role]
            for ip in ips:
                deploy_and_execute_script(ip, KEY_FILE_PATH, script)

    logger.info("Script execution completed.")
