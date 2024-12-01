#!/bin/bash

# Constants
DB_ROOT_PASSWORD=${1:-default_password}
LOG_FILE="/var/log/mysql_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Starting MySQL setup..."

# Update package lists
if ! sudo apt-get update; then
    echo "Error updating package lists" >&2
    exit 1
fi

# Install MySQL Server
echo "Installing MySQL Server..."
sudo debconf-set-selections <<< "mysql-server mysql-server/root_password password $DB_ROOT_PASSWORD"
sudo debconf-set-selections <<< "mysql-server mysql-server/root_password_again password $DB_ROOT_PASSWORD"
sudo apt-get install -y mysql-server || exit 1

# Secure MySQL Installation
echo "Securing MySQL installation..."
sudo mysql -u root -p"$DB_ROOT_PASSWORD" -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$DB_ROOT_PASSWORD';"
sudo mysql -u root -p"$DB_ROOT_PASSWORD" -e "DELETE FROM mysql.user WHERE User='';"
sudo mysql -u root -p"$DB_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS test;"
sudo mysql -u root -p"$DB_ROOT_PASSWORD" -e "FLUSH PRIVILEGES;"

# Configure MySQL to allow external connections
sudo sed -i 's/bind-address\s*=.*$/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
sudo systemctl restart mysql

# Install Sakila Sample Database
echo "Installing Sakila database..."
wget https://downloads.mysql.com/docs/sakila-db.tar.gz
tar xzf sakila-db.tar.gz

if mysql -u root -p"$DB_ROOT_PASSWORD" -e "USE sakila;" 2>/dev/null; then
    echo "Sakila database already exists. Skipping import."
else
    mysql -u root -p"$DB_ROOT_PASSWORD" -e "CREATE DATABASE sakila;"
    mysql -u root -p"$DB_ROOT_PASSWORD" sakila < sakila-db/sakila-schema.sql
    mysql -u root -p"$DB_ROOT_PASSWORD" sakila < sakila-db/sakila-data.sql
fi

rm -rf sakila-db sakila-db.tar.gz

# Install Sysbench
echo "Installing Sysbench..."
sudo apt-get install -y sysbench || exit 1

# Prepare and Run Sysbench
echo "Running Sysbench benchmarks..."
sysbench /usr/share/sysbench/oltp_read_only.lua \
  --mysql-db=sakila \
  --mysql-user=root \
  --mysql-password="$DB_ROOT_PASSWORD" \
  prepare

sysbench /usr/share/sysbench/oltp_read_only.lua \
  --mysql-db=sakila \
  --mysql-user=root \
  --mysql-password="$DB_ROOT_PASSWORD" \
  run

echo "MySQL setup and benchmarking complete."
