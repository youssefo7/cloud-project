import json
import boto3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS resources
ec2 = boto3.resource('ec2')
s3 = boto3.client('s3')  # S3 client

# Global variable to store instance details
INSTANCE_DETAILS = {}

def retrieve_instance_ips_by_role(save_to_file=True, upload_to_s3=False, bucket_name=None):
    """
    Retrieve instance public and private IPs by role, save to a JSON file, and optionally upload to S3.
    """
    roles = ['manager', 'worker', 'proxy', 'gatekeeper', 'trusted_host']
    instance_ips = {}
    for role in roles:
        instances = ec2.instances.filter(
            Filters=[
                {'Name': 'tag:Role', 'Values': [role]},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
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

    # Save to JSON file if required
    if save_to_file:
        with open('instance_details.json', 'w') as f:
            json.dump(instance_ips, f, indent=4)
        logger.info("Instance details saved to 'instance_details.json'.")

    # Optionally upload to S3
    if upload_to_s3 and bucket_name:
        try:
            s3.upload_file('instance_details.json', bucket_name, 'instance_details.json')
            logger.info(f"Instance details uploaded to S3 bucket '{bucket_name}'.")
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")

    # Update the global variable
    global INSTANCE_DETAILS
    INSTANCE_DETAILS = instance_ips
    logger.info("Instance details updated in global variable.")

    return instance_ips


def load_instance_details(file_path='instance_details.json'):
    """
    Load instance details from a JSON file into the global variable.
    """
    global INSTANCE_DETAILS
    try:
        with open(file_path, 'r') as f:
            INSTANCE_DETAILS = json.load(f)
        logger.info("Instance details loaded from file.")
    except FileNotFoundError:
        logger.error(f"File '{file_path}' not found. Run the retrieval function first.")
        INSTANCE_DETAILS = None


if __name__ == "__main__":
    BUCKET_NAME = "instances-details" 
    retrieve_instance_ips_by_role(save_to_file=True, upload_to_s3=True, bucket_name=BUCKET_NAME)
