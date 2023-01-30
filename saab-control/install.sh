#!/bin/bash

# Check if the script is being run as root
if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root." 1>&2
   exit 1
fi

# Define the service file
service_file=saab.service

# Check if the service file exists
if [ ! -f "$service_file" ]; then
   echo "Service file not found: $service_file" 1>&2
   exit 1
fi

# Copy the service file to the systemd directory
cp $service_file /etc/systemd/system/

# Reload the systemd configuration
systemctl daemon-reload

# Enable the service to start on boot
systemctl enable saab

# Start the service
systemctl start saab

echo "Installation complete."
