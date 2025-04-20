# Server Provisioning Requirements for LiveKit

## Purpose

This document outlines the tried and tested server specifications, network configurations, DNS settings, and access credentials required before you begin the manual LiveKit installation process described in the separate second part of this readme.

## Server Requirements Verification

Confirm the provisioned server meets these specifications:

- Operating System: Ubuntu 24.04 LTS (or a compatible recent Debian/Ubuntu version).
- Instance Size: Minimum 4 vCPU / 4 GB RAM
- Static IP Address: The server must have the static public IP address 65.109.11.13 assigned to it. This is critical for our Africastalking integration.

## Network Firewall Verification

Confirm that the cloud provider's firewall rules allow inbound traffic to the IP address 65.109.11.13 on the following ports:

- TCP/22: From your specific Admin IP(s) (for SSH)
- TCP/443: From Anywhere (0.0.0.0/0)
- TCP/7881: From Anywhere (0.0.0.0/0)
- UDP/3478: From Anywhere (0.0.0.0/0)
- UDP/50000-60000: From Anywhere (0.0.0.0/0)
- UDP/5060: From Anywhere or specific known SIP provider IPs
- UDP/10000-20000: From Anywhere or specific known SIP provider IPs
- TCP/7880: From Anywhere (0.0.0.0/0)
- TCP/5349: From Anywhere (0.0.0.0/0)

## DNS Verification

DNS A records should be created and propagated, this domain will be used as the primary endpoint for LiveKit SDKs, i.e wss://livekit.outbound.im. certs will be obtained in the second part of this config by me using `caddy`.

- livekit.outbound.im must resolve to 65.109.11.13.
- livekit-turn.outbound.im must resolve to 65.109.11.13.

You can verify this using dig or nslookup from your local machine or another server:

## Next Steps

Once all the above points are met (Server Specs, IP Address, Firewall, DNS, SSH Access) I can proceed with the installation steps outlined below.

# Manual LiveKit Setup Steps

Here's a breakdown of the steps to manually configure LiveKit on your existing server based on the provided cloud-init script:

**Important Considerations Before You Start:**

1.  **Existing Services:** Check if any services conflict with what LiveKit uses (e.g., ports 443, 7880, 7881, 5349, 3478, 5060, 6379, 50000-60000 UDP, 10000-20000 UDP).
2.  **Firewall:** The script uses `iptables`. Check your current rules (`sudo iptables -L -v -n`) before adding new ones. These steps assume `iptables`.
3.  **Permissions:** Most of these commands will require `sudo`. I'll need sudo access
4.  **API Keys:** The script uses placeholder API keys (`APIKEYXXXXXXXXXX`, `SECRETKEYXXXXXXXXXXXXXXXXXXX`). **You MUST generate your own unique keys and replace these placeholders** in the configuration files (`livekit.yaml`, `egress.yaml`, `docker-compose.yaml`). ps. I typically just used one I've generated before from lk cloud project. just to maintain the format.
5.  **Domain Names:** The configuration uses `livekit.example.com` and `livekit-turn.example.com` (based on your latest script). **Ensure you replace these with your actual domain names** that point correctly to your Debian server's public IP address in your DNS settings. Caddy will try to get Let's Encrypt certificates for these.
6.  **OS:** These instructions assume a Debian/Ubuntu-based system.

**Steps:**

**1. Update Package Lists and Upgrade Packages**

- Update the list of available packages:
  ```bash
  sudo apt update
  ```
- Upgrade installed packages (run this during a maintenance window if possible, as it can restart services):
  ```bash
  sudo apt upgrade -y
  ```

**2. Install Required Packages**

- Install Docker, Python, Git, and other utilities. Also install `iptables-persistent` to save firewall rules (this package provides the `netfilter-persistent` command).

  ```bash
  sudo apt install -y \
  docker.io \
  python3 python3-venv python3-pip \
  git nano curl \
  netfilter-persistent iptables-persistent
  ```

**3. Install AppArmor (Required for Docker on Debian)**

- Install AppArmor and related utilities:

  ```bash
  sudo apt install -y apparmor apparmor-utils
  ```

**3. Create Necessary Directories**

- Create directories for LiveKit configuration and Caddy data:
  ```bash
  sudo mkdir -p /opt/livekit/caddy_data
  sudo mkdir -p /usr/local/bin
  ```

**4. Create Configuration Files**

- Use a text editor like `nano` to create the following files with the specified content.
- **CRITICAL:** Remember to replace `APIKEYXXXXXXXXXX` and `SECRETKEYXXXXXXXXXXXXXXXXXXX` with your actual generated API Key and Secret.
- **CRITICAL:** Remember to replace `livekit.example.com` and `livekit-turn.example.com` with your actual domain names.

  - **LiveKit Config (`/opt/livekit/livekit.yaml`):**

    ```bash
    sudo nano /opt/livekit/livekit.yaml
    ```

    Paste the following content (replace keys and domain!):

    ```yaml
    port: 7880
    bind_addresses:
      - ""
    rtc:
      tcp_port: 7881
      port_range_start: 50000
      port_range_end: 60000
      use_external_ip: true
      enable_loopback_candidate: false
    redis:
      address: localhost:6379
      username: ""
      password: ""
      db: 0
      use_tls: false
      sentinel_master_name: ""
      sentinel_username: ""
      sentinel_password: ""
      sentinel_addresses: []
      cluster_addresses: []
      max_redirects: null
    turn:
      enabled: true
      domain: livekit-turn.example.com # <-- REPLACE DOMAIN
      tls_port: 5349
      udp_port: 3478
      external_tls: true
    keys:
      APIKEYXXXXXXXXXX: SECRETKEYXXXXXXXXXXXXXXXXXXX # <-- REPLACE KEYS
    ```

  - **Egress Config (`/opt/livekit/egress.yaml`):**

    ```bash
    sudo nano /opt/livekit/egress.yaml
    ```

    Paste the following content (replace keys!):

    ```yaml
    api_key: "APIKEYXXXXXXXXXX" # <-- REPLACE KEY
    api_secret: "SECRETKEYXXXXXXXXXXXXXXXXXXX" # <-- REPLACE SECRET
    ws_url: ws://localhost:7880
    insecure: true # because we're just using ws://
    redis:
      address: localhost:6379
    log_level: debug
    ```

  - **Caddy Config (`/opt/livekit/caddy.yaml`):**

    ```bash
    sudo nano /opt/livekit/caddy.yaml
    ```

    Paste the following content (replace domains!):

    ```yaml
    logging:
      logs:
        default:
          level: INFO
    storage:
      "module": "file_system"
      "root": "/data"
    apps:
      tls:
        certificates:
          automate:
            - livekit.example.com # <-- REPLACE DOMAIN
            - livekit-turn.example.com # <-- REPLACE DOMAIN
      layer4:
        servers:
          main:
            listen: [":443"]
            routes:
              - match:
                  - tls:
                      sni:
                        - "livekit-turn.example.com" # <-- REPLACE DOMAIN
                handle:
                  - handler: tls
                  - handler: proxy
                    upstreams:
                      - dial: ["localhost:5349"] # This IP might be updated by update_ip.sh later
              - match:
                  - tls:
                      sni:
                        - "livekit.example.com" # <-- REPLACE DOMAIN
                handle:
                  - handler: tls
                    connection_policies:
                      - alpn: ["http/1.1"]
                  - handler: proxy
                    upstreams:
                      - dial: ["localhost:7880"]
    ```

  - **IP Update Script (`/opt/livekit/update_ip.sh`):**

    ```bash
    sudo nano /opt/livekit/update_ip.sh
    ```

    Paste the following content:

    ```bash
    #!/usr/bin/env bash
    ip=`ip addr show |grep "inet " |grep -v 127.0.0. |head -1|cut -d" " -f6|cut -d/ -f1`
    sed -i.orig -r "s/\\\"(.+)(\:5349)/\\\"$ip\2/" /opt/livekit/caddy.yaml
    ```

    _Note: This script attempts to find the server's primary non-loopback IP and insert it into the Caddy config for the TURN server proxy. Verify it finds the correct IP on your system._

  - **Docker Compose Config (`/opt/livekit/docker-compose.yaml`):**

    ```bash
    sudo nano /opt/livekit/docker-compose.yaml
    ```

    Paste the following content (replace keys in the `sip` service!):

    ```yaml
    # This docker-compose requires host networking, which is only available on Linux
    # This compose will not function correctly on Mac or Windows
    services:
      caddy:
        image: livekit/caddyl4
        command: run --config /etc/caddy.yaml --adapter yaml
        restart: unless-stopped
        network_mode: "host"
        volumes:
          - ./caddy.yaml:/etc/caddy.yaml
          - ./caddy_data:/data
      livekit:
        image: livekit/livekit-server:latest
        command: --config /etc/livekit.yaml
        restart: unless-stopped
        network_mode: "host"
        volumes:
          - ./livekit.yaml:/etc/livekit.yaml
      redis:
        image: redis:7-alpine
        command: redis-server /etc/redis.conf
        restart: unless-stopped
        network_mode: "host"
        volumes:
          - ./redis.conf:/etc/redis.conf
          - ./redis_data:/data # Note: cloud-init didn't create this dir, Docker will
      sip:
        image: livekit/sip:latest
        network_mode: host
        environment:
          SIP_CONFIG_BODY: |
            api_key: 'APIKEYXXXXXXXXXX' # <-- REPLACE KEY
            api_secret: 'SECRETKEYXXXXXXXXXXXXXXXXXXX' # <-- REPLACE SECRET
            ws_url: 'ws://localhost:7880'
            redis:
              address: 'localhost:6379'
            sip_port: 5060
            rtp_port: 10000-20000
            use_external_ip: true
            logging:
              level: debug
      egress:
        image: livekit/egress:latest
        network_mode: "host"
        restart: unless-stopped
        # needed for Chrome sandboxing in the container
        cap_add:
          - SYS_ADMIN
        environment:
          # Tells the egress image where to read its .yaml configuration
          EGRESS_CONFIG_FILE: /etc/egress.yaml
        volumes:
          - ./egress.yaml:/etc/egress.yaml
    ```

  - **Systemd Service File (`/etc/systemd/system/livekit-docker.service`):**

    ```bash
    sudo nano /etc/systemd/system/livekit-docker.service
    ```

    Paste the following content:

    ```ini
    [Unit]
    Description=LiveKit Server Container
    After=docker.service
    Requires=docker.service

    [Service]
    LimitNOFILE=500000
    Restart=always
    WorkingDirectory=/opt/livekit
    # Shutdown container (if running) when unit is started
    ExecStartPre=/usr/local/bin/docker-compose -f docker-compose.yaml down
    ExecStart=/usr/local/bin/docker-compose -f docker-compose.yaml up
    ExecStop=/usr/local/bin/docker-compose -f docker-compose.yaml down

    [Install]
    WantedBy=multi-user.target
    ```

  - **Redis Config (`/opt/livekit/redis.conf`):**
    ```bash
    sudo nano /opt/livekit/redis.conf
    ```
    Paste the following content:
    ```ini
    bind 127.0.0.1 ::1
    protected-mode yes
    port 6379
    timeout 0
    tcp-keepalive 300
    ```

**5. Configure Firewall Rules (iptables)**

- **Check existing rules first:** `sudo iptables -L INPUT -v -n --line-numbers` to avoid conflicts.
- Add the necessary rules to allow traffic on LiveKit ports. The `-I INPUT 1` inserts the rule at the top.
  ```bash
  sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
  sudo iptables -I INPUT 1 -p tcp --dport 5349 -j ACCEPT
  sudo iptables -I INPUT 1 -p tcp --dport 7880 -j ACCEPT
  sudo iptables -I INPUT 1 -p tcp --dport 7881 -j ACCEPT
  sudo iptables -I INPUT 1 -p udp --dport 3478 -j ACCEPT
  sudo iptables -I INPUT 1 -p udp --dport 50000:60000 -j ACCEPT
  sudo iptables -I INPUT 1 -p udp --dport 5060 -j ACCEPT
  sudo iptables -I INPUT 1 -p udp --dport 10000:20000 -j ACCEPT
  ```
- Save the rules so they persist after reboot:
  ```bash
  sudo netfilter-persistent save
  ```
  _(If prompted during `iptables-persistent` installation or when running save, agree to save current IPv4 and IPv6 rules)._

**6. Install Docker Compose**

- Download the specified version of Docker Compose:
  ```bash
  sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  ```
- Make it executable:
  ```bash
  sudo chmod 755 /usr/local/bin/docker-compose
  ```
- Verify installation:
  ```bash
  docker-compose --version
  ```

**7. Prepare and Run IP Update Script**

- Make the IP update script executable:
  ```bash
  sudo chmod 755 /opt/livekit/update_ip.sh
  ```
- Run the script to potentially update the IP in `caddy.yaml`:
  ```bash
  sudo /opt/livekit/update_ip.sh
  ```
- **Verify the change:** Check `/opt/livekit/caddy.yaml` to ensure the IP address for the `localhost:5349` dial string was correctly updated if needed. If the script didn't find the right IP, you may need to edit `/opt/livekit/caddy.yaml` manually.

**8. Enable and Start the LiveKit Service**

- Reload the systemd daemon to recognize the new service file:
  ```bash
  sudo systemctl daemon-reload
  ```
- Enable the service to start automatically on boot:
  ```bash
  sudo systemctl enable livekit-docker
  ```
- Start the LiveKit service (this will run `docker-compose down` first, then `docker-compose up`):
  ```bash
  sudo systemctl start livekit-docker
  ```

**9. Verify Installation**

- Check the status of the service:
  ```bash
  sudo systemctl status livekit-docker
  ```
- Check the Docker container logs:
  ```bash
  cd /opt/livekit
  sudo /usr/local/bin/docker-compose logs -f
  ```
  (Look for errors, especially related to Caddy getting certificates or services connecting).
- Test LiveKit functionality using the [LiveKit Example Tools](https://docs.livekit.io/guides/getting-started/example-tools/) or your own application, pointing to `wss://<your-livekit-domain.com>` (using the domain you configured).
