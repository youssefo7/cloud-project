import requests
import time

# Proxy Configuration
PROXY_IP = "34.201.20.117"  # Replace with your proxy's public IP
PROXY_PORT = 5000            # The port your proxy server is running on
PROXY_URL = f"http://{PROXY_IP}:{PROXY_PORT}"

MODES = ["direct_hit", "random", "customized"]

# Test Data
TEST_DB = "sakila"
TEST_TABLE = "proxy_test"
TEST_DATA = {"id": 4, "data": "proxy_test_data"}

def test_via_proxy():
    for mode in MODES:
        print(f"\nTesting mode: {mode}")

        # Step 1: Set Proxy Mode
        response = requests.post(f"{PROXY_URL}/set_mode/{mode}")
        if response.status_code == 200:
            print(f"Proxy mode set to {mode}")
        else:
            print(f"Failed to set mode {mode}: {response.text}")
            continue

        # Step 2a: Use Sakila Database
        print("Switching to Sakila database through Proxy...")
        use_db_query = "USE sakila;"
        response = requests.post(f"{PROXY_URL}/query", json={"query": use_db_query})
        if response.status_code == 200:
            print(f"Database switched to 'sakila'")
        else:
            print(f"Failed to switch to 'sakila': {response.text}")
            continue

        # Step 2b: Create Table
        print("Creating table through Proxy...")
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {TEST_TABLE} (
            id INT PRIMARY KEY,
            data VARCHAR(255)
        );
        """
        response = requests.post(f"{PROXY_URL}/query", json={"query": create_table_query})
        if response.status_code == 200:
            print(f"Table creation successful")
        else:
            print(f"Table creation failed: {response.text}")
            continue

        # Step 2c: Insert Data
        print("Inserting data through Proxy...")
        insert_query = f"""
        INSERT INTO {TEST_TABLE} (id, data) VALUES
        ({TEST_DATA['id']}, '{TEST_DATA['data']}')
        ON DUPLICATE KEY UPDATE data = '{TEST_DATA['data']}';
        """
        response = requests.post(f"{PROXY_URL}/query", json={"query": insert_query})
        if response.status_code == 200:
            print(f"Insert successful")
            print("Waiting for replication to complete...")
            time.sleep(5)  # Wait for replication to complete
        else:
            print(f"Insert failed: {response.text}")
            continue

        # Step 3: Read Data
        print("Reading data through Proxy...")
        select_query = f"SELECT * FROM {TEST_TABLE};"
        response = requests.post(f"{PROXY_URL}/query", json={"query": select_query})
        if response.status_code == 200:
            result = response.json()
            print(f"Read successful: {result}")
            if any(row['id'] == TEST_DATA['id'] and row['data'] == TEST_DATA['data'] for row in result.get('results', [])):
                print(f"Data verified successfully in mode {mode}.")
            else:
                print(f"Data mismatch in mode {mode}.")
        else:
            print(f"Read failed: {response.text}")
            


if __name__ == "__main__":
    test_via_proxy()
