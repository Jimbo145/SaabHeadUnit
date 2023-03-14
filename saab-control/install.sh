#!/bin/bash

# Check if the script is being run as root
if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root." 1>&2
   exit 1
fi

# Define the service file
service_file=saab.service
update_file=saab_update.service

# Check if the service file exists
if [ ! -f "$service_file" ]; then
   echo "Service file not found: $service_file" 1>&2
   exit 1
fi

# Copy the service file to the systemd directory
cp $update_file /etc/systemd/system/

# Copy the Updater to
cp $service_file /etc/systemd/system/

mkdir -p /usr/local/bin/SaabHeadUnitUpdater/
cp saabUpdate.py /usr/local/bin/SaabHeadUnitUpdater/

# Reload the systemd configuration
systemctl daemon-reload

# Enable the service to start on boot
systemctl enable saab_update
systemctl enable saab

# Start the service
systemctl start saab_update
systemctl start saab

echo "Installation complete."
