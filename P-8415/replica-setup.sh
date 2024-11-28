#!/bin/bash

ROLE=$1  # "manager" or "worker"
MASTER_IP=$2  # Manager's IP address
MASTER_LOG_FILE=$3  # Log file from manager
MASTER_LOG_POS=$4  # Log position from manager

# Credentials
ROOT_PASSWORD="YOUR_ROOT_PASSWORD"
REPL_USER="replicator"
REPL_PASSWORD="replica_password"

# Test user credentials
TEST_USER="test_user"
TEST_PASSWORD="test_password"

if [[ "$ROLE" == "manager" ]]; then
    echo "Configuring as Manager..."

    # Update MySQL configuration
    sudo sed -i '/\[mysqld\]/a \
server-id=1\n\
log_bin=/var/log/mysql/mysql-bin.log\n\
binlog_format=ROW' /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo sed -i 's/^bind-address\s*=.*$/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo systemctl restart mysql

    # Create and configure replication user
    mysql -u root -p"$ROOT_PASSWORD" -e "
    DROP USER IF EXISTS '$REPL_USER'@'%';
    CREATE USER '$REPL_USER'@'%' IDENTIFIED BY '$REPL_PASSWORD';
    GRANT REPLICATION SLAVE ON *.* TO '$REPL_USER'@'%';
    FLUSH PRIVILEGES;"

    # Create test_user for local access
    mysql -u root -p"$ROOT_PASSWORD" -e "
    DROP USER IF EXISTS '$TEST_USER'@'localhost';
    CREATE USER '$TEST_USER'@'localhost' IDENTIFIED BY '$TEST_PASSWORD';
    GRANT ALL PRIVILEGES ON sakila.* TO '$TEST_USER'@'localhost';
    FLUSH PRIVILEGES;"

    # Show master status
    mysql -u root -p"$ROOT_PASSWORD" -e "SHOW MASTER STATUS;"

elif [[ "$ROLE" == "worker" ]]; then
    echo "Configuring as Worker..."

    # Update MySQL configuration
    sudo sed -i "/\[mysqld\]/a \
server-id=$((RANDOM % 1000 + 2))\n\
relay_log=/var/log/mysql/mysql-relay-bin.log\n\
read_only=1" /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo systemctl restart mysql

    # Reset slave and configure replication
    mysql -u root -p"$ROOT_PASSWORD" -e "
    STOP SLAVE;
    RESET SLAVE ALL;
    CHANGE MASTER TO
        MASTER_HOST='$MASTER_IP',
        MASTER_USER='$REPL_USER',
        MASTER_PASSWORD='$REPL_PASSWORD',
        MASTER_LOG_FILE='$MASTER_LOG_FILE',
        MASTER_LOG_POS=$MASTER_LOG_POS,
        GET_MASTER_PUBLIC_KEY=1;
    START SLAVE;"

    # Create test_user for local access
    mysql -u root -p"$ROOT_PASSWORD" -e "
    DROP USER IF EXISTS '$TEST_USER'@'localhost';
    CREATE USER '$TEST_USER'@'localhost' IDENTIFIED BY '$TEST_PASSWORD';
    GRANT ALL PRIVILEGES ON sakila.* TO '$TEST_USER'@'localhost';
    FLUSH PRIVILEGES;"

    # Show slave status
    mysql -u root -p"$ROOT_PASSWORD" -e "SHOW SLAVE STATUS\G"
else
    echo "Invalid role specified or unsupported configuration."
fi
