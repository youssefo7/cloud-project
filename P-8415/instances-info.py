import json
import boto3
import logging
import time
from constants import PROXY_USER, REPLICATION_USER, DB_DETAILS  # Import required constants

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS resources
ec2 = boto3.resource('ec2')

# Global variable to store instance details
INSTANCE_DETAILS = {}

import time

def retrieve_instance_ips_by_role(save_to_file=True):
    """
    Retrieve instance public and private IPs by role, save to a JSON file.
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
            # Wait until public IP is assigned
            timeout = 60  # seconds
            interval = 5  # seconds
            elapsed = 0
            while instance.public_ip_address is None and elapsed < timeout:
                logger.info(f"Waiting for public IP assignment for instance {instance.id}")
                time.sleep(interval)
                elapsed += interval
                instance.reload()
            if instance.public_ip_address is None:
                logger.error(f"No public IP assigned to instance {instance.id} after {timeout} seconds.")
            public_ips.append(instance.public_ip_address)
            private_ips.append(instance.private_ip_address)
        instance_ips[role] = {
            'public_ips': public_ips,
            'private_ips': private_ips
        }

    # Add user credentials and DB details
    instance_ips['proxy_user'] = {
        'name': PROXY_USER['name'],
        'password': PROXY_USER['password']
    }
    instance_ips['replication_user'] = {
        'name': REPLICATION_USER['name'],
        'password': REPLICATION_USER['password']
    }
    instance_ips['db_details'] = DB_DETAILS

    # Save to JSON file if required
    if save_to_file:
        with open('instance_details.json', 'w') as f:
            json.dump(instance_ips, f, indent=4)
        logger.info("Instance details saved to 'instance_details.json'.")

    # Update the global variable
    global INSTANCE_DETAILS
    INSTANCE_DETAILS = instance_ips
    logger.info("Instance details updated in global variable.")

    return instance_ips

if __name__ == "__main__":
    retrieve_instance_ips_by_role(save_to_file=True)
