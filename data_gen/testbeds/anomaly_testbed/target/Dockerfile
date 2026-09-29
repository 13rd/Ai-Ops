FROM debian:bookworm-slim

# Tooling the SSH MetricsCollector/ContainerCollector and the `anomaly` control
# script rely on: stress-ng + dd (load), procps/net-tools/iproute2/sysstat
# (/proc readers), openssh-server (collection transport).
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server \
        stress-ng \
        procps \
        coreutils \
        iproute2 \
        net-tools \
        sysstat \
        sudo \
        curl \
        gnupg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Current docker CLI (client only) from Docker's official repo. Debian's bundled
# docker.io is API 1.41 — too old for modern daemons (min 1.44), so the collector's
# `docker ps` would fail. docker-ce-cli is multi-arch and negotiates down.
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# 'demo' SSH user. Password is set at RUNTIME from $SSH_PASSWORD (entrypoint),
# never baked into an image layer. NOPASSWD sudo so the injector can run the
# anomaly workloads.
RUN mkdir -p /var/run/sshd \
    && useradd --create-home --shell /bin/bash demo \
    && echo "demo ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    && sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && ssh-keygen -A

COPY anomaly /usr/local/bin/anomaly
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/anomaly /usr/local/bin/entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
