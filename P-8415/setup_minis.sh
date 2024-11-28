#!/bin/bash

# Update package lists
sudo apt-get update

# Install MySQL Server
sudo apt-get install -y mysql-server

# Secure MySQL Installation
# Set root password and remove anonymous users and test database
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'YOUR_ROOT_PASSWORD';"
sudo mysql -e "DELETE FROM mysql.user WHERE User='';"
sudo mysql -e "DROP DATABASE IF EXISTS test;"
sudo mysql -e "FLUSH PRIVILEGES;"

sudo sed -i 's/bind-address\s*=.*$/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf
sudo systemctl restart mysql

# Install the Sakila sample database
wget https://downloads.mysql.com/docs/sakila-db.tar.gz
tar xzf sakila-db.tar.gz

# Import the Sakila database
mysql -u root -pYOUR_ROOT_PASSWORD -e "CREATE DATABASE sakila;"
mysql -u root -pYOUR_ROOT_PASSWORD sakila < sakila-db/sakila-schema.sql
mysql -u root -pYOUR_ROOT_PASSWORD sakila < sakila-db/sakila-data.sql

# Install Sysbench
sudo apt-get install -y sysbench

# Prepare the database for Sysbench
sysbench /usr/share/sysbench/oltp_read_only.lua \
  --mysql-db=sakila \
  --mysql-user=root \
  --mysql-password=YOUR_ROOT_PASSWORD \
  prepare

# Run Sysbench Benchmark
sysbench /usr/share/sysbench/oltp_read_only.lua \
  --mysql-db=sakila \
  --mysql-user=root \
  --mysql-password=YOUR_ROOT_PASSWORD \
  run

echo "MySQL setup and benchmarking complete."
