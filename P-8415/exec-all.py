import subprocess
import logging
import datetime

# Configure logging
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = f'automation_log_{timestamp}.log'

logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger()

def run_script(script_name, *args):
    """
    Runs a Python script with optional arguments and logs the output.

    :param script_name: Name of the script to run.
    :param args: Additional arguments for the script.
    """
    logger.info(f"Starting {script_name} with arguments: {args}")
    try:
        command = ['python', script_name] + list(args)
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"{script_name} completed successfully.")
        logger.info(f"Output:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"Warnings/Errors from {script_name}:\n{result.stderr}")
    except subprocess.CalledProcessError as e:
        logger.error(f"{script_name} failed with return code {e.returncode}")
        logger.error(f"Error output:\n{e.stderr}")
        exit(1)  # Exit if a critical script fails

def main():
    """
    Orchestrates the deployment pipeline by running scripts sequentially.
    """
    # Run `instances_deploy.py` with both arguments
    run_script('instances_deploy.py', '--create-instances', '--setup-aws-resources')

    # Continue with other scripts
    scripts_to_run = [
        'instances-info.py',  # Generates instance information
        'instances_setup.py'  # Sets up instances (e.g., replication, proxy)
    ]

    for script in scripts_to_run:
        run_script(script)

if __name__ == '__main__':
    main()
