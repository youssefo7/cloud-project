#!/bin/bash

# Assign arguments to variables
MANAGER_IP="$1"
WORKER_IPS="$2"  # Comma-separated list of worker IPs

# Update package lists
sudo apt-get update

# Install ProxySQL
wget https://github.com/sysown/proxysql/releases/download/v2.0.17/proxysql_2.0.17-ubuntu20_amd64.deb
sudo dpkg -i proxysql_2.0.17-ubuntu20_amd64.deb

# Start ProxySQL
sudo systemctl start proxysql

# Configure ProxySQL
# Login to ProxySQL admin interface
sudo mysql -u admin -padmin -h 127.0.0.1 -P6032 <<EOF

-- Add MySQL servers
-- Manager node
INSERT INTO mysql_servers (hostgroup_id, hostname, port) VALUES (10, '$MANAGER_IP', 3306);

EOF

# Split WORKER_IPS and insert each worker
IFS=',' read -ra ADDR <<< "$WORKER_IPS"
for WORKER_IP in "${ADDR[@]}"; do
sudo mysql -u admin -padmin -h 127.0.0.1 -P6032 <<EOF
INSERT INTO mysql_servers (hostgroup_id, hostname, port) VALUES (20, '$WORKER_IP', 3306);
EOF
done

sudo mysql -u admin -padmin -h 127.0.0.1 -P6032 <<EOF

-- Add users
INSERT INTO mysql_users (username, password, default_hostgroup) VALUES ('root', '', 10);

-- Load to runtime and save
LOAD MYSQL SERVERS TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;

LOAD MYSQL USERS TO RUNTIME;
SAVE MYSQL USERS TO DISK;
EOF

# Implement Proxy Patterns

# Direct Hit Pattern
sudo mysql -u admin -padmin -h 127.0.0.1 -P6032 <<EOF

DELETE FROM mysql_query_rules;

-- Direct Hit rule: All traffic to manager (hostgroup 10)
INSERT INTO mysql_query_rules (rule_id, active, match_pattern, destination_hostgroup) VALUES (1, 1, '.*', 10);

LOAD MYSQL QUERY RULES TO RUNTIME;
SAVE MYSQL QUERY RULES TO DISK;
EOF

# Random Selection Pattern
# To implement Random Selection, comment out the Direct Hit rules and uncomment the following:

# sudo mysql -u admin -padmin -h 127.0.0.1 -P6032 <<EOF

# DELETE FROM mysql_query_rules;

# -- Write queries to manager (hostgroup 10)
# INSERT INTO mysql_query_rules (rule_id, active, match_pattern, negate_match_pattern, destination_hostgroup, apply) \
# VALUES (1, 1, '^SELECT', 1, 10, 1);

# -- Read queries to workers (hostgroup 20)
# INSERT INTO mysql_query_rules (rule_id, active, match_pattern, destination_hostgroup, apply) \
# VALUES (2, 1, '^SELECT', 20, 1);

# LOAD MYSQL QUERY RULES TO RUNTIME;
# SAVE MYSQL QUERY RULES TO DISK;
# EOF

# Customized Selection Pattern based on ping time
# Enable monitoring and configure replication hostgroups

sudo mysql -u admin -padmin -h 127.0.0.1 -P6032 <<EOF

-- Enable monitoring
SET mysql-monitor_username='monitor';
SET mysql-monitor_password='';

-- Configure replication hostgroups
INSERT INTO mysql_replication_hostgroups (writer_hostgroup, reader_hostgroup, comment) VALUES (10, 20, 'Replication hostgroups');

LOAD MYSQL VARIABLES TO RUNTIME;
SAVE MYSQL VARIABLES TO DISK;

LOAD MYSQL SERVERS TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;
EOF

# Create the monitoring user on backend servers (manager and workers)
for HOST in "$MANAGER_IP" "${ADDR[@]}"; do
  mysql -h "$HOST" -u root -e "CREATE USER IF NOT EXISTS 'monitor'@'%' IDENTIFIED WITH mysql_native_password;"
  mysql -h "$HOST" -u root -e "GRANT USAGE ON *.* TO 'monitor'@'%';"
done

# Restart ProxySQL to apply changes
sudo systemctl restart proxysql

echo "Proxy server setup complete."
