import pymysql
import random
import sqlparse
import ping3
from flask import Flask, request

# Configuration
MANAGER = {"host": "54.83.100.242", "user": "proxyuser", "password": "proxy", "db": "sakila", "port": 3306}
WORKERS = [
    {"host": "44.222.228.71", "user": "proxyuser", "password": "proxy", "db": "sakila", "port": 3306},
    {"host": "54.83.100.242", "user": "proxyuser", "password": "proxy", "db": "sakila", "port": 3306},
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
            best_worker = min(latencies, key=latencies.get)
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
