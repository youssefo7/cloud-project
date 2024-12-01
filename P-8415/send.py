import requests
import time

# Gatekeeper Configuration
GATEKEEPER_URL = "http://54.204.115.107:5000"  # Replace with Gatekeeper's public IP
MODES = ["direct_hit", "random", "customized"]

# Test Data
TEST_DB = "sakila"
TEST_TABLE = "cock"
TEST_DATA = {"id": 4, "data": "proxy_test"}

def test_via_gatekeeper():
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

        # Step 2c: Insert Data via Gatekeeper
        print("Inserting data through Gatekeeper...")
        insert_query = f"""
        INSERT INTO {TEST_TABLE} (id, data) VALUES
        ({TEST_DATA['id']}, '{TEST_DATA['data']}')
        ON DUPLICATE KEY UPDATE data = '{TEST_DATA['data']}';
        """
        response = requests.post(f"{GATEKEEPER_URL}/filter", json={"query": insert_query})
        if response.status_code == 200:
            print(f"Insert successful: {response.json()}")
            print("Waiting for replication to complete...")
            time.sleep(2)  # Wait for replication
        else:
            print(f"Insert failed: {response.text}")
            continue

        # Step 3: Read Data via Gatekeeper
        print("Reading data through Gatekeeper...")
        select_query = f"SELECT * FROM {TEST_TABLE};"
        response = requests.post(f"{GATEKEEPER_URL}/filter", json={"query": select_query})
        if response.status_code == 200:
            result = response.json()
            print(f"Read successful: {result}")
            if str(TEST_DATA["id"]) in str(result) and TEST_DATA["data"] in str(result):
                print(f"Data verified successfully in mode {mode}.")
            else:
                print(f"Data mismatch in mode {mode}.")
        else:
            print(f"Read failed: {response.text}")

if __name__ == "__main__":
    test_via_gatekeeper()
