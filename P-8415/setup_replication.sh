#!/bin/bash

ROLE=$1                # "manager" or "worker"
MASTER_IP=$2           # Manager's IP address (for workers)
MASTER_LOG_FILE=$3     # Log file from manager (for workers)
MASTER_LOG_POS=$4      # Log position from manager (for workers)
ROOT_PASSWORD=$5       # Root password for MySQL
REPL_USER=$6           # Replication user name
REPL_PASSWORD=$7       # Replication user password
PROXY_USER=$8          # Proxy user name
PROXY_PASSWORD=$9      # Proxy user password

if [[ -z "$ROOT_PASSWORD" || -z "$REPL_USER" || -z "$REPL_PASSWORD" || -z "$PROXY_USER" || -z "$PROXY_PASSWORD" ]]; then
    echo "Error: ROOT_PASSWORD, REPL_USER, REPL_PASSWORD, PROXY_USER, and PROXY_PASSWORD must be provided."
    exit 1
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

wait_for_mysql() {
    log "Waiting for MySQL to be ready..."
    until mysqladmin ping -u root -p"$ROOT_PASSWORD" --silent; do
        sleep 2
    done
    log "MySQL is ready."
}

if [[ "$ROLE" == "manager" ]]; then
    log "Configuring as Manager..."

    # Update MySQL configuration for replication
    sudo sed -i '/\[mysqld\]/a \
server-id=1\n\
log_bin=/var/log/mysql/mysql-bin.log\n\
binlog_format=MIXED\n\
binlog_ignore_db=mysql' /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo sed -i 's/^bind-address\s*=.*$/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo systemctl restart mysql
    wait_for_mysql

    # Create replication user with necessary privileges
    mysql -u root -p"$ROOT_PASSWORD" -e "
    CREATE USER IF NOT EXISTS '$REPL_USER'@'%' IDENTIFIED BY '$REPL_PASSWORD';
    GRANT REPLICATION SLAVE ON *.* TO '$REPL_USER'@'%';
    GRANT SELECT ON sakila.* TO '$REPL_USER'@'%';
    FLUSH PRIVILEGES;"

    # Create proxy user with necessary privileges
    mysql -u root -p"$ROOT_PASSWORD" -e "
    CREATE USER IF NOT EXISTS '$PROXY_USER'@'%' IDENTIFIED BY '$PROXY_PASSWORD';
    GRANT SELECT, INSERT, UPDATE, DELETE, CREATE ON sakila.* TO '$PROXY_USER'@'%';
    FLUSH PRIVILEGES;"

    # Show master status for workers
    MASTER_STATUS=$(mysql -u root -p"$ROOT_PASSWORD" -e "SHOW MASTER STATUS\G")
    log "Master Status: $MASTER_STATUS"


elif [[ "$ROLE" == "worker" ]]; then
    log "Configuring as Worker..."

    # Ensure master details are provided
    if [[ -z "$MASTER_IP" || -z "$MASTER_LOG_FILE" || -z "$MASTER_LOG_POS" ]]; then
        log "Error: MASTER_IP, MASTER_LOG_FILE, and MASTER_LOG_POS must be provided."
        exit 1
    fi

    # Update MySQL configuration for replication
    sudo sed -i "/\[mysqld\]/a \
server-id=$((RANDOM % 1000 + 2))\n\
relay_log=/var/log/mysql/mysql-relay-bin.log\n\
read_only=1" /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo sed -i 's/^bind-address\s*=.*$/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
    sudo systemctl restart mysql
    wait_for_mysql

    # Create proxy user with necessary privileges before setting super_read_only
    mysql -u root -p"$ROOT_PASSWORD" -e "
    CREATE USER IF NOT EXISTS '$PROXY_USER'@'%' IDENTIFIED BY '$PROXY_PASSWORD';
    GRANT SELECT ON sakila.* TO '$PROXY_USER'@'%';
    FLUSH PRIVILEGES;"

    # Now set super_read_only
    mysql -u root -p"$ROOT_PASSWORD" -e "SET GLOBAL super_read_only = 1;"

    # Configure replication
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

    # Show slave status for debugging
    SLAVE_STATUS=$(mysql -u root -p"$ROOT_PASSWORD" -e "SHOW SLAVE STATUS\G")
    log "Slave Status: $SLAVE_STATUS"

else
    log "Invalid role specified. Must be 'manager' or 'worker'."
    exit 1
fi

log "$ROLE configuration complete."
