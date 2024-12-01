import requests
import time

# Gatekeeper Configuration
GATEKEEPER_URL = "http://34.232.46.111:5000"  
MODES = ["direct_hit", "random", "customized"]

# Test Data
TEST_DB = "sakila"
TEST_TABLE = "proxy_test"
TEST_DATA = {"id": 1, "data": "proxy_test_data"}

def send_write_request(session, query):
    response = session.post(f"{GATEKEEPER_URL}/filter", json={"query": query})
    return response

def send_read_request(session, query):
    response = session.post(f"{GATEKEEPER_URL}/filter", json={"query": query})
    return response

def test_via_gatekeeper():
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

        # Step 2a: Use Sakila Database via Gatekeeper
        print("Switching to Sakila database through Gatekeeper...")
        use_db_query = "USE sakila;"
        response = requests.post(f"{GATEKEEPER_URL}/filter", json={"query": use_db_query})
        if response.status_code == 200:
            print(f"Database switched to 'sakila': {response.json()}")
        else:
            print(f"Failed to switch to 'sakila': {response.text}")
            continue

        # Step 2b: Create Table via Gatekeeper
        print("Creating table through Gatekeeper...")
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {TEST_TABLE} (
            id INT PRIMARY KEY,
            data VARCHAR(255)
        );
        """
        response = requests.post(f"{GATEKEEPER_URL}/filter", json={"query": create_table_query})
        if response.status_code == 200:
            print(f"Table creation successful: {response.json()}")
        else:
            print(f"Table creation failed: {response.text}")
            continue

        # Write one record
        print("Sending one write request...")
        write_query = f"""
        INSERT INTO {TEST_TABLE} (id, data) VALUES
        ({TEST_DATA['id']}, '{TEST_DATA['data']}')
        ON DUPLICATE KEY UPDATE data = '{TEST_DATA['data']}';
        """
        with requests.Session() as session:
            response = send_write_request(session, write_query)
            if response.status_code == 200:
                print("Write request successful.")
            else:
                print(f"Write request failed: {response.text}")
                continue

        # Wait for replication to complete
        print("Waiting for replication to complete...")
        time.sleep(5)

        # Read the inserted record
        print("Sending one read request...")
        select_query = f"SELECT * FROM {TEST_TABLE} WHERE id = {TEST_DATA['id']};"
        with requests.Session() as session:
            response = send_read_request(session, select_query)
            if response.status_code == 200:
                result = response.json()
                if any(row['id'] == TEST_DATA['id'] and row['data'] == TEST_DATA['data'] for row in result.get('results', [])):
                    print("Data verified successfully.")
                else:
                    print(f"Data mismatch or not found: {result}")
            else:
                print(f"Read request failed: {response.text}")

if __name__ == "__main__":
    test_via_gatekeeper()
