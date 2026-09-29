FROM debian:bookworm-slim

# stress-ng + standard CLI tools used by MetricsCollector via SSH.
# iperf3 generates real eth0 traffic for the network_storm anomaly (loopback
# traffic is ignored by the collector, which greps only eth*/ens*/enp*).
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server \
        stress-ng \
        iperf3 \
        curl \
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

# Anomaly generator, baked in so the standalone stand can run it via docker exec.
COPY anomaly.sh /usr/local/bin/demo_anomaly.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/demo_anomaly.sh /usr/local/bin/entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
