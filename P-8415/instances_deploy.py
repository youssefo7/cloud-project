import boto3
import logging
import argparse
import requests
import os
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

# Dynamically retrieve your public IP and append CIDR suffix
try:
    MY_PUBLIC_IP = f"{requests.get('https://checkip.amazonaws.com').text.strip()}/32"
    logger.info(f"Your public IP: {MY_PUBLIC_IP}")
except requests.RequestException as e:
    logger.error(f"Failed to retrieve public IP: {e}")
    MY_PUBLIC_IP = "0.0.0.0/0"  # Fallback to allow all traffic if IP retrieval fails

SECURITY_GROUP_CONFIGS = {
    "gatekeeper": {
        "Description": "Gatekeeper security group",
        "Inbound": [
            (5000, "0.0.0.0/0"),  # Allow external access to Gatekeeper
            (22, MY_PUBLIC_IP),  # Allow SSH from your IP
        ],
    },
    "trusted_host": {
        "Description": "Trusted Host security group",
        "Inbound": [
            (5000, "gatekeeper"),  # Allow traffic from Gatekeeper SG
            (22, MY_PUBLIC_IP),  # Allow SSH from your IP
        ],
    },
    "proxy": {
        "Description": "Proxy security group",
        "Inbound": [
            (5000, "trusted_host"),  # Allow traffic from Trusted Host SG
            (22, MY_PUBLIC_IP),    # Allow SSH from your IP
        ],
    },
    "manager": {
        "Description": "Manager security group",
        "Inbound": [
            (3306, "proxy"),   # Allow MySQL traffic from Proxy SG
            (3306, "worker"),  # Allow MySQL traffic from Worker SG for replication
            (22, MY_PUBLIC_IP),  # Allow SSH from your IP
        ],
    },
    "worker": {
        "Description": "Worker security group",
        "Inbound": [
            (3306, "proxy"),   # Allow MySQL traffic from Proxy SG
            (3306, "manager"), # Allow MySQL traffic from Manager SG for replication
            (22, MY_PUBLIC_IP),  # Allow SSH from your IP
        ],
    },
}

def create_or_update_security_group(role, description):
    """Create a security group and return its ID."""
    try:
        response = ec2_client.create_security_group(GroupName=role, Description=description)
        sg_id = response['GroupId']
        logger.info(f"Created security group '{role}' with ID: {sg_id}")
        return sg_id
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            response = ec2_client.describe_security_groups(GroupNames=[role])
            sg_id = response['SecurityGroups'][0]['GroupId']
            logger.info(f"Security group '{role}' already exists with ID: {sg_id}")
            return sg_id
        else:
            logger.error(f"Error creating security group for {role}: {e}")
            raise

def apply_security_group_rules(sg_id, inbound_rules, security_groups):
    """Apply inbound rules to an existing security group."""
    ip_permissions = []
    for port, source in inbound_rules:
        ip_permissions.append({
            'IpProtocol': 'tcp',
            'FromPort': port,
            'ToPort': port,
            'IpRanges': [{'CidrIp': source}] if '/' in source else [],
            'UserIdGroupPairs': [{'GroupId': security_groups[source]}] if source in security_groups else [],
        })

    ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=ip_permissions)
    logger.info(f"Ingress rules set for security group with ID: {sg_id}")

def create_key_pair(key_name, key_file_path):
    try:
        ec2_client.describe_key_pairs(KeyNames=[key_name])
        logger.info(f"Key pair '{key_name}' already exists.")
    except ClientError as e:
        if 'InvalidKeyPair.NotFound' in str(e):
            key_pair = ec2_client.create_key_pair(KeyName=key_name)
            with open(key_file_path, 'w') as file:
                file.write(key_pair['KeyMaterial'])
            os.chmod(key_file_path, 0o400)
            logger.info(f"Created key pair '{key_name}' and saved to '{key_file_path}'.")
        else:
            logger.error(f"Error checking for key pair '{key_name}': {e}")
            raise

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AWS EC2 Deployment Script')
    parser.add_argument('--create-instances', action='store_true', help='Create new instances')
    parser.add_argument('--setup-aws-resources', action='store_true', help='Setup AWS resources (key pair, security groups)')
    args = parser.parse_args()

    if args.setup_aws_resources:
        create_key_pair(KEY_NAME, KEY_FILE_PATH)
        security_groups = {}

        # Step 1: Create all security groups
        for role, config in SECURITY_GROUP_CONFIGS.items():
            sg_id = create_or_update_security_group(role, config['Description'])
            security_groups[role] = sg_id

        # Step 2: Apply inbound rules to all security groups
        for role, config in SECURITY_GROUP_CONFIGS.items():
            sg_id = security_groups[role]
            apply_security_group_rules(sg_id, config['Inbound'], security_groups)

    if args.create_instances:
        default_subnet_id = get_default_subnet_id()
        if not default_subnet_id:
            logger.error("Cannot proceed without a default subnet.")
            exit(1)

        for role, config in SECURITY_GROUP_CONFIGS.items():
            sg_id = security_groups[role]
            count = 1 if role != "worker" else 2
            instance_type = "t2.large" if role in ["proxy", "gatekeeper", "trusted_host"] else "t2.micro"
            launch_and_wait_instances(role, count, instance_type, sg_id, default_subnet_id)

    logger.info("Deployment completed.")
