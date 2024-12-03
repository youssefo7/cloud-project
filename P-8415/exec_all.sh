#!/bin/bash

# Check if Python3 is installed
if ! command -v python3 &> /dev/null
then
    echo "Python3 is not installed. Please install Python3 to proceed."
    exit 1
fi

# Execute the Python script
echo "Starting the Python script 'exec_all.py'..."
python3 exec_all.py

# Check if the script ran successfully
if [ $? -eq 0 ]; then
    echo "Script 'exec_all.py' executed successfully!"
else
    echo "Script 'exec_all.py' encountered an error."
    exit 1
fi
