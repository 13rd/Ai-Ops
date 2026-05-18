FROM debian:bookworm-slim

# stress-ng + standard CLI tools used by MetricsCollector via SSH
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server \
        stress-ng \
        procps \
        coreutils \
        iproute2 \
        net-tools \
        sudo \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/run/sshd \
    && useradd --create-home --shell /bin/bash demo \
    && echo "demo:demopass" | chpasswd \
    && echo "demo ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && ssh-keygen -A

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
