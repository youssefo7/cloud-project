import pymysql
import random
import sqlparse
import ping3
import socket
import time
from flask import Flask, request

# Configuration
MANAGER = {"host": "3.91.194.246", "user": "proxyuser", "password": "proxy", "db": "sakila", "port": 3306}
WORKERS = [
    {"host": "34.224.173.230", "user": "proxyuser", "password": "proxy", "db": "sakila", "port": 3306},
    {"host": "54.89.156.156", "user": "proxyuser", "password": "proxy", "db": "sakila", "port": 3306},
]

app = Flask(__name__)
mode = "direct_hit"  # Default mode


def connect_to_db(config):
    """Establish a connection to a MySQL instance."""
    return pymysql.connect(**config)


def parse_query(query):
    """Determine if the query is a read or write."""
    parsed = sqlparse.parse(query)[0]
    query_type = parsed.get_type()
    return query_type.upper()




def test_tcp_latency(host, port=3306):
    """Measure the latency to a MySQL instance using TCP."""
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=2):
            return time.time() - start
    except Exception:
        return None  # Return None for unreachable hosts

def validate_replication(worker):
    """Check if the worker is caught up with replication."""
    try:
        connection = connect_to_db(worker)
        with connection.cursor() as cursor:
            cursor.execute("SHOW SLAVE STATUS;")
            status = cursor.fetchone()
            if status:
                return status["Seconds_Behind_Master"] == 0  # Ensure no replication lag
    except Exception as e:
        print(f"Error validating replication for {worker['host']}: {e}")
    return False

def route_query(query):
    """Route the query based on the mode."""
    query_type = parse_query(query)
    if mode == "direct_hit":
        return connect_to_db(MANAGER)
    elif mode == "random":
        if query_type == "SELECT":
            return connect_to_db(random.choice(WORKERS))
        else:
            return connect_to_db(MANAGER)
    elif mode == "customized":
        if query_type == "SELECT":
            latencies = {worker["host"]: ping3.ping(worker["host"]) for worker in WORKERS}
            print(f"Calculated latencies: {latencies}")  # Debug logging
            available_workers = {host: latency for host, latency in latencies.items() if latency is not None}
            if not available_workers:
                raise Exception("No reachable or up-to-date workers available for customized mode")
            best_worker = min(available_workers, key=available_workers.get)
            print(f"Selected worker for query: {best_worker}")  # Debug logging
            return connect_to_db(next(w for w in WORKERS if w["host"] == best_worker))
        else:
            return connect_to_db(MANAGER)
    else:
        raise ValueError(f"Unknown mode: {mode}")




@app.route("/query", methods=["POST"])
def handle_query():
    query = request.json.get("query")
    try:
        connection = route_query(query)
        with connection.cursor() as cursor:
            cursor.execute(query)
            if cursor.description:
                return {"results": cursor.fetchall()}
            else:
                connection.commit()
                return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/set_mode/<new_mode>", methods=["POST"])
def set_mode(new_mode):
    global mode
    if new_mode not in ["direct_hit", "random", "customized"]:
        return {"error": "Invalid mode"}, 400
    mode = new_mode
    return {"status": f"Mode set to {new_mode}"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3306)
