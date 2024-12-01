import requests
import time

# Gatekeeper Configuration
GATEKEEPER_URL = "http://34.232.46.111:5000"  # Replace with your Gatekeeper's public IP
MODES = ["direct_hit", "random", "customized"]

# Test Data
TEST_TABLE = "proxy_test"

def send_write_request(session, query):
    """Send a write request to the Gatekeeper."""
    response = session.post(f"{GATEKEEPER_URL}/filter", json={"query": query})
    return response

def send_read_request(session, query):
    """Send a read request to the Gatekeeper."""
    response = session.post(f"{GATEKEEPER_URL}/filter", json={"query": query})
    return response

def benchmark_via_gatekeeper():
    """Perform benchmarking for each mode."""
    print(f"Using Gatekeeper URL: {GATEKEEPER_URL}")
    
    for mode in MODES:
        print(f"\nTesting mode: {mode}")

        # Step 1: Set Proxy Mode via Gatekeeper
        response = requests.post(f"{GATEKEEPER_URL}/filter", json={"query": f"SET_MODE {mode}"})
        if response.status_code == 200:
            print(f"Proxy mode set to {mode}")
        else:
            print(f"Failed to set mode {mode}: {response.text}")
            continue

        # Step 2: Prepare the Test Table
        print("Setting up the test table...")
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {TEST_TABLE} (
            id INT PRIMARY KEY,
            data VARCHAR(255)
        );
        """
        response = requests.post(f"{GATEKEEPER_URL}/filter", json={"query": create_table_query})
        if response.status_code != 200:
            print(f"Failed to create test table: {response.text}")
            continue

        # Start benchmarking
        start_time = time.time()

        # Step 3: Send 1000 Write Requests
        print("Sending 1000 write requests...")
        write_query_template = f"""
        INSERT INTO {TEST_TABLE} (id, data) VALUES
        (%s, 'TestData%s')
        ON DUPLICATE KEY UPDATE data = 'TestData%s';
        """
        with requests.Session() as session:
            for i in range(1, 1001):
                write_query = write_query_template % (i, i, i)
                response = send_write_request(session, write_query)
                if response.status_code != 200:
                    print(f"Write request {i} failed: {response.text}")
                if i % 100 == 0:
                    print(f"{i} write requests sent.")

        # Wait for replication to complete
        print("Waiting for replication to complete...")
        time.sleep(10)  # Increased wait time for replication

        # Step 4: Send 1000 Read Requests
        print("Sending 1000 read requests...")
        select_query_template = f"SELECT * FROM {TEST_TABLE} WHERE id = %s;"
        with requests.Session() as session:
            for i in range(1, 5):
                select_query = select_query_template % i
                response = send_read_request(session, select_query)
                if response.status_code == 200:
                    result = response.json()
                    # Validate the data
                    expected_data = f"TestData{i}"
                    if not any(row["id"] == i and row["data"] == expected_data for row in result.get("results", [])):
                        print(f"Data mismatch for id {i}: Expected {expected_data}, got {result}")
                else:
                    print(f"Read request {i} failed: {response.text}")
                if i % 100 == 0:
                    print(f"{i} read requests sent.")

        # End benchmarking
        end_time = time.time()
        total_time = end_time - start_time
        print(f"Benchmark for mode {mode} completed in {total_time:.2f} seconds.")

if __name__ == "__main__":
    benchmark_via_gatekeeper()
