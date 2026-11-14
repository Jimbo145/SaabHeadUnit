FROM debian:bullseye

# Install necessary packages
# RUN apt-get update && apt-get install -y init systemd systemd-cron systemd-sysv bash sudo git python3 python3-pip libsystemd-dev gcc pkg-config


RUN apt-get update \
    && apt-get install --no-install-recommends -y init git python3-dev systemd libsystemd-dev systemd-sysv rsyslog systemd-cron ca-certificates python3-pip pkg-config build-essential iproute2 kmod \
    # Fix a bug with common-debian script
    && rm -f /usr/local/bin/systemctl 
    #  Clean up


ARG USERNAME=pi
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Create the user
RUN groupadd --gid $USER_GID $USERNAME \
&& useradd --uid $USER_UID --create-home --gid $USER_GID -m $USERNAME \
&& apt-get update \
&& apt-get install -y sudo \
&& echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
&& chmod 0440 /etc/sudoers.d/$USERNAME

RUN apt-get install -y x11-xserver-utils iputils-ping

# Add pi to sudoers list

# Create a directory for the devcontainer
RUN mkdir /home/devcontainer

# Copy the necessary files to the devcontainer directory
COPY --chown=1 /* /home/devcontainer

# Install Python dependencies
# RUN pip3 install -r /home/devcontainer/requirements.txt

# RUN apt-get install -y x11-xserver-utils iputils-ping

# Expose systemd
VOLUME [ "/sys/fs/cgroup" ]

# CMD ["/sbin/init"]
CMD ["/lib/systemd/systemd", "--system", "--unit=basic.target"]