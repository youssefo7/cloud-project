import requests
import time

# Proxy Configuration
PROXY_URL = "http://44.222.224.7:3306"  # Replace with your proxy's public IP
MODES = ["direct_hit", "random", "customized"]

# Test Data
TEST_DB = "sakila"
TEST_TABLE = "replication_test"
TEST_DATA = {"id": 3, "data": "proxy_test"}

def test_proxy():
    for mode in MODES:
        print(f"\nTesting mode: {mode}")
        
        # Step 1: Set Proxy Mode
        response = requests.post(f"{PROXY_URL}/set_mode/{mode}")
        if response.status_code == 200:
            print(f"Proxy mode set to {mode}")
        else:
            print(f"Failed to set mode {mode}: {response.text}")
            continue

        # Step 2a: Create Table through Proxy
        print("Creating table through Proxy...")
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {TEST_DB}.{TEST_TABLE} (
            id INT PRIMARY KEY,
            data VARCHAR(255)
        );
        """
        create_table_data = {
            "query": create_table_query
        }
        response = requests.post(f"{PROXY_URL}/query", json=create_table_data)
        if response.status_code == 200:
            print(f"Table creation successful: {response.json()}")
        else:
            print(f"Table creation failed: {response.text}")
            continue

        # Step 2b: Insert Data through Proxy
        print("Inserting data through Proxy...")
        insert_query = f"""
        INSERT INTO {TEST_DB}.{TEST_TABLE} (id, data) VALUES
        ({TEST_DATA['id']}, '{TEST_DATA['data']}')
        ON DUPLICATE KEY UPDATE data = '{TEST_DATA['data']}';
        """
        insert_data = {
            "query": insert_query
        }
        print(f"Insert Query: {insert_query}")
        response = requests.post(f"{PROXY_URL}/query", json=insert_data)
        if response.status_code == 200:
            print(f"Insert successful: {response.json()}")
        else:
            print(f"Insert failed: {response.text}")
            continue

        # Step 3: Read Data through Proxy
        print("Reading data through Proxy...")
        select_data = {
            "query": f"SELECT * FROM {TEST_DB}.{TEST_TABLE};"
        }
        response = requests.post(f"{PROXY_URL}/query", json=select_data)
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
    test_proxy()
