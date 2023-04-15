#!/bin/bash

# Check if the script is being run as root
if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root." 1>&2
   exit 1
fi

# Define the service file
service_file=saab.service
update_file=saab_update.service
REPO_URL="https://github.com/Jimbo145/SaabHeadUnit.git"
REPO_DIR="/usr/local/bin/SaabHeadUnitUpdater/"

# Check if the service file exists
if [ ! -f "$service_file" ]; then
   echo "Service file not found: $service_file" 1>&2
   exit 1
fi

# Copy the service file to the systemd directory
cp $update_file /etc/systemd/system/

# Copy the Updater to
cp $service_file /etc/systemd/system/


mkdir -p "$REPO_DIR"

# Check if the repository already exists
if [ -d "$REPO_DIR/SaabHeadUnit/" ]; then
  # If the repository exists, pull the latest changes
  cd "$REPO_DIR/SaabHeadUnit/"
  git pull
else
  # If the repository doesn't exist, clone it
  git clone "$REPO_URL" "$REPO_DIR/SaabHeadUnit/"
fi

cp /usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit/saab-control/saabUpdate.py /usr/local/bin/SaabHeadUnitUpdater/

# force saabUpdate to copy files
touch /usr/local/bin/SaabHeadUnitUpdater/update

pip3 install -r  /usr/local/bin/SaabHeadUnitUpdater/SaabHeadUnit/saab-control/requirements.txt


# Reload the systemd configuration
systemctl daemon-reload

# Enable the service to start on boot
systemctl enable saab_update

# Start the service
systemctl start saab_update

echo "Installation complete."
