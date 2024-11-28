#!/bin/bash

# Variables
PROXY_IP="127.0.0.1"
PROXY_PORT="6032"  # Admin port
PROXY_QUERY_PORT="6033"  # Query port
PROXY_ADMIN_USER="admin"
PROXY_ADMIN_PASS="admin"
PROXY_DB_USER="proxyuser"
PROXY_DB_PASS="proxy_password"
DB="sakila"
TABLE="replication_test"
LOG_FILE="/tmp/proxysql_test.log"


# Function to set implementation
set_mode() {
    MODE=$1
    echo "Setting ProxySQL mode to $MODE..." | tee -a $LOG_FILE
    case $MODE in
        direct_hit)
            mysql -u $PROXY_ADMIN_USER -p$PROXY_ADMIN_PASS -h $PROXY_IP -P $PROXY_PORT <<EOF
UPDATE mysql_query_rules SET active = 0;
UPDATE mysql_query_rules SET active = 1 WHERE rule_id = 1; -- Direct Hit
LOAD MYSQL QUERY RULES TO RUNTIME;
EOF
            ;;
        random)
            mysql -u $PROXY_ADMIN_USER -p$PROXY_ADMIN_PASS -h $PROXY_IP -P $PROXY_PORT <<EOF
UPDATE mysql_query_rules SET active = 0;
UPDATE mysql_query_rules SET active = 1 WHERE rule_id IN (2, 3); -- Random
LOAD MYSQL QUERY RULES TO RUNTIME;
EOF
            ;;
        customized)
            mysql -u $PROXY_ADMIN_USER -p$PROXY_ADMIN_PASS -h $PROXY_IP -P $PROXY_PORT <<EOF
UPDATE mysql_query_rules SET active = 0;
UPDATE mysql_query_rules SET active = 1 WHERE rule_id IN (4, 5); -- Customized
LOAD MYSQL QUERY RULES TO RUNTIME;
EOF
            ;;
        *)
            echo "Invalid mode specified. Choose: direct_hit, random, customized." | tee -a $LOG_FILE
            exit 1
            ;;
    esac
    echo "Mode set to $MODE." | tee -a $LOG_FILE
}

# Function to test queries
test_queries() {
    echo "Testing queries in mode $1..." | tee -a $LOG_FILE

    # Insert data through ProxySQL
    echo "Inserting data through ProxySQL..." | tee -a $LOG_FILE
    mysql -u $PROXY_DB_USER -p$PROXY_DB_PASS -h $PROXY_IP -P $PROXY_QUERY_PORT <<EOF
USE $DB;
CREATE TABLE IF NOT EXISTS $TABLE (id INT PRIMARY KEY, data VARCHAR(255));
INSERT INTO $TABLE (id, data) VALUES (1, 'proxy_test') ON DUPLICATE KEY UPDATE data = 'proxy_test';
EOF

    # Read data through ProxySQL
    echo "Reading data through ProxySQL..." | tee -a $LOG_FILE
    mysql -u $PROXY_DB_USER -p$PROXY_DB_PASS -h $PROXY_IP -P $PROXY_QUERY_PORT <<EOF
USE $DB;
SELECT * FROM $TABLE;
EOF

    # Log where the query was routed
    echo "Query routed to (check logs on master and slaves)..." | tee -a $LOG_FILE
}

# Main execution
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <direct_hit|random|customized>"
    exit 1
fi

MODE=$1
set_mode $MODE
test_queries $MODE
echo "Testing completed for mode $MODE. Check logs at $LOG_FILE." | tee -a $LOG_FILE
