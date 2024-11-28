#!/bin/bash

# Variables
MASTER_HOST="3.91.215.132"  # Replace with your master node's IP
SLAVE1_HOST="52.201.51.167" # Replace with your first slave node's IP
SLAVE2_HOST="54.221.53.102" # Replace with your second slave node's IP
PROXYSQL_ADMIN_USER="admin"
PROXYSQL_ADMIN_PASS="admin"

# Install MySQL client
echo "Installing MySQL client..."
sudo apt-get install -y mysql-client

# Install ProxySQL
echo "Installing ProxySQL..."
wget -O - 'https://repo.proxysql.com/ProxySQL/repo_pub_key' | sudo apt-key add -
echo "deb https://repo.proxysql.com/ProxySQL/proxysql-2.4.x/$(lsb_release -sc)/ ./ " | sudo tee /etc/apt/sources.list.d/proxysql.list
sudo apt-get update
sudo apt-get install -y proxysql

# Start ProxySQL service
echo "Starting ProxySQL service..."
sudo systemctl start proxysql
sudo systemctl enable proxysql

# Configure ProxySQL
echo "Configuring ProxySQL..."
mysql -u $PROXYSQL_ADMIN_USER -p$PROXYSQL_ADMIN_PASS -h 127.0.0.1 -P6032 <<EOF

-- Add master to hostgroup 1 (Direct Hit - all traffic to master)
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (1, '$MASTER_HOST', 3306);

-- Add master and slaves to hostgroup 2 (Random - random read, write to master)
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (2, '$MASTER_HOST', 3306);
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (2, '$SLAVE1_HOST', 3306);
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (2, '$SLAVE2_HOST', 3306);

-- Add master and one optimized slave to hostgroup 3 (Customized - best latency slave)
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (3, '$MASTER_HOST', 3306);
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (3, '$SLAVE1_HOST', 3306); -- Default optimized slave
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (4, '$SLAVE2_HOST', 3306);

-- Create query rules for Direct Hit (all queries to master)
INSERT INTO mysql_query_rules(rule_id, match_pattern, destination_hostgroup, apply) VALUES (1, '.*', 1, 0);

-- Create query rules for Random (writes to master, reads to random slaves)
INSERT INTO mysql_query_rules(rule_id, match_pattern, destination_hostgroup, apply) VALUES (2, '^(INSERT|UPDATE|DELETE|REPLACE).*$', 2, 0);
INSERT INTO mysql_query_rules(rule_id, match_pattern, destination_hostgroup, apply) VALUES (3, '^SELECT.*$', 2, 0);

-- Create query rules for Customized (writes to master, reads to optimized slave)
INSERT INTO mysql_query_rules(rule_id, match_pattern, destination_hostgroup, apply) VALUES (4, '^(INSERT|UPDATE|DELETE|REPLACE).*$', 3, 0);
INSERT INTO mysql_query_rules(rule_id, match_pattern, destination_hostgroup, apply) VALUES (5, '^SELECT.*$', 3, 0);

-- Load configuration into runtime and save to disk
LOAD MYSQL SERVERS TO RUNTIME;
LOAD MYSQL QUERY RULES TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;
SAVE MYSQL QUERY RULES TO DISK;
EOF

echo "ProxySQL setup complete with all modes configured."
