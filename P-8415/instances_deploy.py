import boto3
import logging
import argparse
import requests
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS resources
ec2 = boto3.resource('ec2')
ec2_client = boto3.client('ec2')

# Constants
KEY_NAME = 'SQL'
INSTANCE_TAG_PREFIX = 'MySQLCluster'
KEY_FILE_PATH = f'{KEY_NAME}.pem'
AMI_ID = 'ami-005fc0f236362e99f'  # Ubuntu 20.04 LTS in us-east-1

# Dynamically retrieve your public IP
try:
    YOUR_PUBLIC_IP = requests.get('https://checkip.amazonaws.com').text.strip()
    logger.info(f"Your public IP: {YOUR_PUBLIC_IP}")
except requests.RequestException as e:
    logger.error(f"Failed to retrieve public IP: {e}")
    YOUR_PUBLIC_IP = "0.0.0.0/0"  # Fallback to allow all traffic if IP retrieval fails

# Updated Security Group Configurations with more permissive rules
SECURITY_GROUP_CONFIGS = {
    "manager": {
        "Description": "Manager security group",
        "Inbound": [
            (3306, "0.0.0.0/0"),  # Allow MySQL traffic from anywhere
            (22, "0.0.0.0/0"),    # Allow SSH from anywhere
        ],
    },
    "worker": {
        "Description": "Worker security group",
        "Inbound": [
            (3306, "0.0.0.0/0"),  # Allow MySQL traffic from anywhere
            (22, "0.0.0.0/0"),    # Allow SSH from anywhere
        ],
    },
    "proxy": {
        "Description": "Proxy security group",
        "Inbound": [
            (5000, "0.0.0.0/0"),  # Allow traffic from anywhere
            (22, "0.0.0.0/0"),    # Allow SSH from anywhere
        ],
    },
    "gatekeeper": {
        "Description": "Gatekeeper security group",
        "Inbound": [
            (5000, "0.0.0.0/0"),  # Allow external access to Gatekeeper
            (22, "0.0.0.0/0"),    # Allow SSH from anywhere
        ],
    },
    "trusted_host": {
        "Description": "Trusted Host security group",
        "Inbound": [
            (5000, "0.0.0.0/0"),  # Allow traffic from anywhere
            (22, "0.0.0.0/0"),    # Allow SSH from anywhere
        ],
    },
}

# Function to parse command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description='AWS EC2 Deployment Script')
    parser.add_argument('--create-instances', action='store_true', help='Create new instances')
    parser.add_argument('--setup-aws-resources', action='store_true', help='Setup AWS resources (key pair, security groups)')
    return parser.parse_args()

# Function to create or update security groups with role-based configurations
def create_or_update_security_group(role, description, inbound_rules, security_groups):
    try:
        # Try to create the security group
        response = ec2_client.create_security_group(GroupName=role, Description=description)
        sg_id = response['GroupId']
        logger.info(f"Created security group '{role}' with ID: {sg_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            # Security group already exists, retrieve its ID
            response = ec2_client.describe_security_groups(GroupNames=[role])
            sg_id = response['SecurityGroups'][0]['GroupId']
            logger.info(f"Security group '{role}' already exists with ID: {sg_id}")
        else:
            logger.error(f"Error creating security group for {role}: {e}")
            raise

    # Store the security group ID for reference
    security_groups[role] = sg_id

    # Revoke existing ingress rules to avoid duplicates
    current_permissions = ec2_client.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0].get('IpPermissions', [])
    if current_permissions:
        ec2_client.revoke_security_group_ingress(GroupId=sg_id, IpPermissions=current_permissions)
        logger.info(f"Revoked existing ingress rules for security group '{role}'")

    # Build new ingress rules
    ip_permissions = []
    for rule in inbound_rules:
        port, sources = rule
        for source in sources.split(","):
            ip_permissions.append({
                'IpProtocol': 'tcp',
                'FromPort': port,
                'ToPort': port,
                'IpRanges': [{'CidrIp': source}]
            })

    # Authorize new ingress rules
    if ip_permissions:
        ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=ip_permissions)
        logger.info(f"Ingress rules set for security group '{role}'")

    return sg_id

# Function to get the default subnet ID
def get_default_subnet_id():
    response = ec2_client.describe_subnets(
        Filters=[{'Name': 'default-for-az', 'Values': ['true']}]
    )
    if response['Subnets']:
        subnet_id = response['Subnets'][0]['SubnetId']
        logger.info(f"Default subnet ID: {subnet_id}")
        return subnet_id
    else:
        logger.error("No default subnet found.")
        return None

# Function to launch instances and wait for them to be ready
def launch_and_wait_instances(role, count, instance_type, sg_id, subnet_id):
    try:
        instances = ec2.create_instances(
            ImageId=AMI_ID,
            MinCount=count,
            MaxCount=count,
            InstanceType=instance_type,
            KeyName=KEY_NAME,
            NetworkInterfaces=[{
                'DeviceIndex': 0,
                'SubnetId': subnet_id,
                'AssociatePublicIpAddress': True,
                'Groups': [sg_id],
            }],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': f'{INSTANCE_TAG_PREFIX}-{role.capitalize()}'},
                    {'Key': 'Role', 'Value': role}
                ]
            }]
        )
        instance_ids = [instance.id for instance in instances]
        logger.info(f"Created instances for role {role}: {instance_ids}")

        for instance_id in instance_ids:
            instance = ec2.Instance(instance_id)
            logger.info(f"Waiting for instance {instance_id} to enter 'running' state...")
            instance.wait_until_running()
            logger.info(f"Instance {instance_id} is now running.")

        return instance_ids
    except Exception as e:
        logger.error(f"Failed to create and wait for instances for {role}: {e}")
        raise

# Main execution logic
if __name__ == "__main__":
    args = parse_arguments()

    if args.setup_aws_resources:
        # Setup security groups
        security_groups = {}
        for role, config in SECURITY_GROUP_CONFIGS.items():
            sg_id = create_or_update_security_group(role, config['Description'], config['Inbound'], security_groups)

    if args.create_instances:
        # Get the default subnet ID
        default_subnet_id = get_default_subnet_id()
        if not default_subnet_id:
            logger.error("Cannot proceed without a default subnet.")
            exit(1)

        # Launch instances and wait for each instance to be ready
        for role, config in SECURITY_GROUP_CONFIGS.items():
            sg_id = security_groups[role]
            count = 1 if role != "worker" else 2
            instance_type = "t2.large" if role in ["proxy", "gatekeeper", "trusted_host"] else "t2.micro"
            launch_and_wait_instances(role, count, instance_type, sg_id, default_subnet_id)

    logger.info("Deployment completed.")
