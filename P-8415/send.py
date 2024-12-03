import requests
import time
import json
import os

# Load Gatekeeper Configuration
CONFIG_FILE_PATH = "instance_details.json"  # Adjust the path if needed

def load_gatekeeper_url():
    """Load the Gatekeeper URL from a local configuration file."""
    try:
        with open(CONFIG_FILE_PATH, "r") as config_file:
            instance_details = json.load(config_file)
            gatekeeper_ip = instance_details['gatekeeper']['public_ips'][0]
            return f"http://{gatekeeper_ip}:5000"
    except (FileNotFoundError, KeyError, IndexError) as e:
        raise Exception(f"Failed to load Gatekeeper URL: {e}")

# Fetch Gatekeeper URL dynamically
try:
    GATEKEEPER_URL = load_gatekeeper_url()
    print(f"Using Gatekeeper URL: {GATEKEEPER_URL}")
except Exception as e:
    print(f"Error: {e}")
    exit(1)

# Test Data
MODES = ["direct_hit", "random", "customized"]
TEST_TABLE = "actor"  # Sakila's `actor` table

def send_write_request(session, query):
    """Send a write request to the Gatekeeper."""
    start_time = time.time()
    response = session.post(f"{GATEKEEPER_URL}/filter", json={"query": query})
    elapsed_time = time.time() - start_time
    return response, elapsed_time

def send_read_request(session, query):
    """Send a read request to the Gatekeeper."""
    start_time = time.time()
    response = session.post(f"{GATEKEEPER_URL}/filter", json={"query": query})
    elapsed_time = time.time() - start_time
    return response, elapsed_time

def benchmark_via_gatekeeper():
    """Perform benchmarking for each mode."""
    for mode in MODES:
        print(f"\nTesting mode: {mode}")

        # Step 1: Set Proxy Mode via Gatekeeper
        response = requests.post(f"{GATEKEEPER_URL}/filter", json={"query": f"SET_MODE {mode}"})
        if response.status_code == 200:
            print(f"Proxy mode set to {mode}")
        else:
            print(f"Failed to set mode {mode}: {response.text}")
            continue

        # Start benchmarking
        start_time = time.time()
        write_times = []
        read_times = []
        data_validation_errors = 0

        # Step 2: Send 1000 Write Requests (to `actor` table)
        print("Sending 1000 write requests...")
        write_query_template = f"""
        INSERT INTO {TEST_TABLE} (actor_id, first_name, last_name) VALUES
        (%s, 'FirstName%s', 'LastName%s')
        ON DUPLICATE KEY UPDATE first_name = 'FirstName%s', last_name = 'LastName%s';
        """
        with requests.Session() as session:
            for i in range(1, 1001):
                write_query = write_query_template % (2000 + i, i, i, i, i)  # Avoid overwriting standard actor IDs
                response, elapsed_time = send_write_request(session, write_query)
                write_times.append(elapsed_time)
                if response.status_code != 200:
                    print(f"Write request {i} failed: {response.text}")
                if i % 100 == 0:
                    print(f"{i} write requests sent.")

        # Wait for replication to complete
        print("Waiting for replication to complete...")
        time.sleep(5)  # Adjust wait time based on replication speed

        # Step 3: Send 1000 Read Requests (to verify writes)
        print("Sending 1000 read requests...")
        read_query_template = f"SELECT * FROM {TEST_TABLE} WHERE actor_id = %s;"
        with requests.Session() as session:
            for i in range(1, 1001):
                read_query = read_query_template % (2000 + i)
                response, elapsed_time = send_read_request(session, read_query)
                read_times.append(elapsed_time)
                if response.status_code == 200:
                    result = response.json()
                    # Validate the data
                    expected_first_name = f"FirstName{i}"
                    expected_last_name = f"LastName{i}"
                    if not any(row["actor_id"] == 2000 + i and row["first_name"] == expected_first_name and row["last_name"] == expected_last_name for row in result.get("results", [])):
                        print(f"Data mismatch for actor_id {2000 + i}: Expected ({expected_first_name}, {expected_last_name}), got {result}")
                        data_validation_errors += 1
                else:
                    print(f"Read request {i} failed: {response.text}")
                if i % 100 == 0:
                    print(f"{i} read requests sent.")

        # End benchmarking
        end_time = time.time()
        total_time = end_time - start_time
        avg_write_time = sum(write_times) / len(write_times)
        avg_read_time = sum(read_times) / len(read_times)

        print(f"\nBenchmark for mode {mode} completed in {total_time:.2f} seconds.")
        print(f"Average write response time: {avg_write_time:.4f} seconds")
        print(f"Average read response time: {avg_read_time:.4f} seconds")
        print(f"Total writes: {len(write_times)}, Total reads: {len(read_times)}")
        print(f"Data validation errors: {data_validation_errors}")

if __name__ == "__main__":
    benchmark_via_gatekeeper()
