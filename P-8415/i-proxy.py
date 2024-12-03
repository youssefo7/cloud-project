import os
import json
import pymysql
import random
import socket
import time
import asyncio
from cachetools import TTLCache
from flask import Flask, request

# Configuration
app = Flask(__name__)
mode = "direct_hit"  # Default mode
INSTANCE_DETAILS = {}

# Load instance details from local file
CONFIG_FILE_PATH = "/home/ubuntu/instance_details.json"

def load_instance_details():
    """Load instance details from local configuration file."""
    global INSTANCE_DETAILS
    try:
        with open(CONFIG_FILE_PATH, "r") as f:
            INSTANCE_DETAILS = json.load(f)
        app.logger.info("Loaded instance details from local configuration file.")
    except Exception as e:
        app.logger.error(f"Failed to load instance details: {e}")
        raise

def connect_to_db(config):
    """Establish a connection to a MySQL instance."""
    try:
        return pymysql.connect(
            host=config["host"],
            user=INSTANCE_DETAILS["proxy_user"]["name"],
            password=INSTANCE_DETAILS["proxy_user"]["password"],
            database=INSTANCE_DETAILS["db_details"]["db_name"],
            port=INSTANCE_DETAILS["db_details"]["port"],
            cursorclass=pymysql.cursors.DictCursor,
        )
    except pymysql.MySQLError as e:
        app.logger.error(f"Database connection failed: {e}")
        raise

def parse_query(query):
    """Determine if the query is a read or write operation."""
    query = query.strip().lower()
    if query.startswith('select'):
        return 'SELECT'
    elif query.startswith('insert'):
        return 'INSERT'
    elif query.startswith('update'):
        return 'UPDATE'
    elif query.startswith('delete'):
        return 'DELETE'
    else:
        return 'OTHER'

# Caching latencies to avoid frequent recalculations
LATENCY_CACHE = TTLCache(maxsize=10, ttl=10)

async def measure_latency_async(host, port=3306):
    """Asynchronously measure TCP latency to a host."""
    loop = asyncio.get_event_loop()
    try:
        start = loop.time()
        await loop.run_in_executor(None, lambda: socket.create_connection((host, port), timeout=2))
        return loop.time() - start
    except Exception:
        return None  # Return None for unreachable hosts

async def get_best_worker_latency_only(worker_configs):
    """Determine the best worker based on latency only."""
    # Use cached latencies if available
    latencies = {worker["host"]: LATENCY_CACHE.get(worker["host"]) for worker in worker_configs}
    
    # Measure latencies asynchronously for uncached workers
    uncached_workers = [worker for worker in worker_configs if worker["host"] not in LATENCY_CACHE]
    if uncached_workers:
        new_latencies = await asyncio.gather(
            *[measure_latency_async(worker["host"], worker["port"]) for worker in uncached_workers]
        )
        for worker, latency in zip(uncached_workers, new_latencies):
            LATENCY_CACHE[worker["host"]] = latency
            latencies[worker["host"]] = latency

    # Filter out workers with unavailable latencies
    available_workers = {
        worker["host"]: latencies[worker["host"]]
        for worker in worker_configs
        if latencies[worker["host"]] is not None
    }
    if not available_workers:
        raise Exception("No reachable workers available for customized mode")

    # Select the worker with the lowest latency
    best_worker_host = min(available_workers, key=available_workers.get)
    return next(worker for worker in worker_configs if worker["host"] == best_worker_host)

async def route_query(query):
    """Route the query based on the mode and type of operation."""
    query_type = parse_query(query)
    app.logger.debug(f"Parsed query type: {query_type}")
    manager_config = {
        "host": INSTANCE_DETAILS["manager"]["private_ips"][0],
        "port": INSTANCE_DETAILS["db_details"]["port"],
    }
    worker_configs = [
        {"host": worker, "port": INSTANCE_DETAILS["db_details"]["port"]}
        for worker in INSTANCE_DETAILS["worker"]["private_ips"]
    ]

    if query_type == "SELECT":  # READ operations
        if mode == "direct_hit":
            connection_config = manager_config
        elif mode == "random":
            connection_config = random.choice(worker_configs)
        elif mode == "customized":
            connection_config = await get_best_worker_latency_only(worker_configs)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        app.logger.info(f"Routing SELECT query to worker: {connection_config['host']}")
    else:  # WRITE and DDL operations
        app.logger.info(f"Routing query of type '{query_type}' to manager")
        connection_config = manager_config

    return connect_to_db(connection_config)

@app.route("/query", methods=["POST"])
def handle_query():
    query = request.json.get("query")
    try:
        app.logger.info(f"Received query: {query}")
        connection = asyncio.run(route_query(query))  # Use asyncio to handle asynchronous routing
        with connection.cursor() as cursor:
            cursor.execute(query)
            if cursor.description:  # SELECT queries return results
                results = cursor.fetchall()
                app.logger.info(f"Query successful. Results: {results}")
                return {"results": results}
            else:  # Other queries commit changes
                connection.commit()
                app.logger.info("Query successful. Changes committed.")
                return {"status": "success"}
    except Exception as e:
        app.logger.error(f"Error handling query: {query}, Error: {e}")
        return {"error": str(e)}, 500

@app.route("/set_mode/<new_mode>", methods=["POST"])
def set_mode(new_mode):
    global mode
    if new_mode not in ["direct_hit", "random", "customized"]:
        return {"error": "Invalid mode"}, 400
    mode = new_mode
    app.logger.info(f"Mode set to {new_mode}")
    return {"status": f"Mode set to {new_mode}"}

if __name__ == "__main__":
    # Load instance details before starting the app
    load_instance_details()
    app.run(host="0.0.0.0", port=5000)
