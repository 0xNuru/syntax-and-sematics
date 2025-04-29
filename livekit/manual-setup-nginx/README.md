# Manual LiveKit Setup Steps (with Nginx)

Here's a breakdown of the steps to manually configure LiveKit on your existing server, using Nginx as the reverse proxy instead of Caddy. This is suitable if another service (like Nginx) is already using port 443.

**Important Considerations Before You Start:**

1.  **Backup:** Before making significant changes, ensure you have a backup or snapshot of your server.
2.  **Existing Nginx:** This guide assumes Nginx is installed and managing port 443. If not, you'll need to install it (`sudo apt install nginx`).
3.  **Other Services:** Check if any services conflict with the _other_ ports LiveKit uses (TCP 7880, 7881, 5349; UDP 3478, 5060, 6379; UDP 10000-20000, 50000-60000).
4.  **Firewall:** The script uses `iptables`. Adapt firewall rules if using `ufw` or another firewall. Check current rules (`sudo iptables -L -v -n`).
5.  **Permissions:** Most commands require `sudo`.
6.  **API Keys:** **You MUST generate your own unique keys** and replace `APIKEYXXXXXXXXXX` / `SECRETKEYXXXXXXXXXXXXXXXXXXX` placeholders.
7.  **Domain Names:** **Ensure you replace `livekit.example.com` and `livekit-turn.example.com` with your actual domain names.** Your primary LiveKit domain (`livekit.example.com`) must point to this server's IP. The TURN domain (`livekit-turn.example.com`) must also point to this server's IP.
8.  **OS:** Assumes Debian/Ubuntu-based system using `apt`.

**Steps:**

**1. Update Package Lists and Upgrade Packages**

- Update package lists:
  ```bash
  sudo apt update
  ```
- Upgrade installed packages:
  ```bash
  sudo apt upgrade -y
  ```

**2. Install Required Packages**

- Install Docker, Python, Git, Certbot (for Nginx SSL), and other utilities. Also install `iptables-persistent`.
  ```bash
  sudo apt install -y docker.io python3 python3-venv python3-pip git nano curl certbot python3-certbot-nginx iptables-persistent nginx
  ```
- Verify Docker is running:
  ```bash
  sudo systemctl status docker
  # If not active: sudo systemctl start docker && sudo systemctl enable docker
  ```
- Verify Nginx is running:
  ```bash
  sudo systemctl status nginx
  # If not active: sudo systemctl start nginx && sudo systemctl enable nginx
  ```

**3. Create Necessary Directories**

- Create directories for LiveKit configuration:
  ```bash
  sudo mkdir -p /opt/livekit
  sudo mkdir -p /usr/local/bin
  # Note: No caddy_data directory needed
  ```

**4. Create Configuration Files (Excluding Caddy)**

- Use `nano` or another editor to create/edit files.
- **CRITICAL:** Replace placeholders for API Keys/Secrets and your actual Domain Names.

  - **LiveKit Config (`/opt/livekit/livekit.yaml`):**

    ```bash
    sudo nano /opt/livekit/livekit.yaml
    ```

    Paste and **edit** (replace keys and domains):

    ```yaml
    port: 7880 # LiveKit listens internally on this port
    bind_addresses:
      - "" # Listen on all interfaces internally
    rtc:
      tcp_port: 7881
      port_range_start: 50000
      port_range_end: 60000
      use_external_ip: true
      enable_loopback_candidate: false
    redis:
      address: localhost:6379
      # ... (rest of redis config)
    turn:
      enabled: true
      domain: livekit-turn.example.com # <-- REPLACE DOMAIN
      tls_port: 5349 # LiveKit handles TLS for TURN on this port
      udp_port: 3478
      external_tls: true # LiveKit handles TLS termination for TURN
    keys:
      APIKEYXXXXXXXXXX: SECRETKEYXXXXXXXXXXXXXXXXXXX # <-- REPLACE KEYS
    ```

  - **Egress Config (`/opt/livekit/egress.yaml`):**

    ```bash
    sudo nano /opt/livekit/egress.yaml
    ```

    Paste and **edit** (replace keys):

    ```yaml
    api_key: "APIKEYXXXXXXXXXX" # <-- REPLACE KEY
    api_secret: "SECRETKEYXXXXXXXXXXXXXXXXXXX" # <-- REPLACE SECRET
    ws_url: ws://localhost:7880 # Connects to LiveKit locally
    insecure: true # Because connection is local (Nginx handles external TLS)
    redis:
      address: localhost:6379
    log_level: debug
    ```

  - **Docker Compose Config (`/opt/livekit/docker-compose.yaml`):**

    ```bash
    sudo nano /opt/livekit/docker-compose.yaml
    ```

    Paste and **edit** (replace keys in `sip` service, **note Caddy service is removed**):

    ```yaml
    # This docker-compose requires host networking
    services:
      # --- Caddy service removed ---
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
          - ./redis_data:/data
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
        cap_add:
          - SYS_ADMIN
        environment:
          EGRESS_CONFIG_FILE: /etc/egress.yaml
        volumes:
          - ./egress.yaml:/etc/egress.yaml
    ```

  - **Systemd Service File (`/etc/systemd/system/livekit-docker.service`):**
    _(This file remains the same as the original setup)_

    ```bash
    sudo nano /etc/systemd/system/livekit-docker.service
    ```

    Paste the following content:

    ```ini
    [Unit]
    Description=LiveKit Server Container (Docker Compose)
    After=docker.service nginx.service # Ensure Docker and Nginx are up
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
    _(This file remains the same as the original setup)_
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

**5. Configure Nginx Reverse Proxy & SSL**

- **Obtain SSL Certificate:** Use Certbot to get a certificate for your main LiveKit domain. Replace `livekit.example.com` with your actual domain.

  ```bash
  sudo certbot --nginx -d livekit.example.com
  # Follow the prompts (enter email, agree to ToS). Choose option 2 (Redirect) if asked.
  ```

  _Note: Certbot will automatically create/modify an Nginx config file for your domain, usually in `/etc/nginx/sites-available/`._

- **Edit Nginx Configuration:** Open the Nginx configuration file created/modified by Certbot (e.g., `/etc/nginx/sites-available/livekit.example.com` or `/etc/nginx/sites-enabled/default`). Find the `server` block for `livekit.example.com` listening on port 443. Add the `location /` block with WebSocket headers inside it.

  ```bash
  sudo nano /etc/nginx/sites-available/your_domain_config_file # Adjust file name
  ```

  Make sure the `server` block for port 443 looks similar to this (add the location block):

  ```nginx
  server {
      listen 443 ssl http2;
      listen [::]:443 ssl http2;
      server_name livekit.example.com; # <-- REPLACE DOMAIN

      # SSL configuration added by Certbot - START
      ssl_certificate /etc/letsencrypt/live/[livekit.example.com/fullchain.pem](https://livekit.example.com/fullchain.pem); # managed by Certbot
      ssl_certificate_key /etc/letsencrypt/live/[livekit.example.com/privkey.pem](https://livekit.example.com/privkey.pem); # managed by Certbot
      include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
      ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
      # SSL configuration added by Certbot - END

      # Add this location block for LiveKit proxying
      location / {
          proxy_pass [http://127.0.0.1:7880](http://127.0.0.1:7880); # Forward to LiveKit container port
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection "Upgrade";
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_read_timeout 86400; # Keep connection open
      }

      # Other directives like root, index, etc. might be present but aren't
      # strictly needed if Nginx only proxies for LiveKit on this domain.
  }
  # Certbot might also add a server block for port 80 redirecting to 443.
  ```

- **Test and Reload Nginx:**

  ```bash
  sudo nginx -t
  # If syntax is OK:
  sudo systemctl reload nginx
  ```

- **Configure Nginx for LiveKit TURN (TCP Proxy):**

  This requires adding a stream block, typically in the main nginx.conf or a file included from it (like in /etc/nginx/conf.d/).

  ```bash
  sudo nano /etc/nginx/nginx.conf
  ```

  Add or ensure a stream {} block exists (outside the http {} block):

  ```nginx
  # Add this block at the top level, alongside the 'http' block
  stream {
      # Define log format for stream if desired (optional)
      # log_format basic '$remote_addr [$time_local] '
      #                  '$protocol $status $bytes_sent $bytes_received '
      #                  '$session_time';
      # access_log /var/log/nginx/stream.log basic;

      # SSL Configuration (repeated for the stream context)
      ssl_certificate /etc/letsencrypt/live/livekit-turn.example.com/fullchain.pem; # <-- CHECK PATH & DOMAIN
      ssl_certificate_key /etc/letsencrypt/live/livekit-turn.example.com/privkey.pem; # <-- CHECK PATH & DOMAIN
      ssl_protocols TLSv1.2 TLSv1.3; # Specify protocols if needed
      ssl_ciphers HIGH:!aNULL:!MD5;  # Specify ciphers if needed
      # ssl_session_cache shared:SSL:10m; # Optional caching
      # ssl_session_timeout 10m; # Optional timeout

      # Server block for TURN over TLS
      server {
          listen 443 ssl; # Nginx listens on 443 for TURN domain
          listen [::]:443 ssl;
          # Ensure this matches the domain for SNI (Server Name Indication)
          # Nginx uses SNI to differentiate this from the HTTP server on the same port.
          # It implicitly uses the domain associated with the SSL certificate.

          # Proxy TCP connections to the internal LiveKit TURN port
          proxy_pass 127.0.0.1:5349;
      }
  }

  ```

  Test and reload the Nginx configuration:

  ```bash
  sudo nginx -t
  # If syntax is OK:
  sudo systemctl reload nginx
  ```

**6. Configure Firewall Rules (iptables)**

- **Check existing rules:** `sudo iptables -L INPUT -v -n --line-numbers`.
- Add rules for Nginx and LiveKit ports (Note: 443 is for Nginx, 5349 is directly for LiveKit TURN).
  ```bash
  sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT  # For Nginx
  sudo iptables -I INPUT 1 -p tcp --dport 5349 -j ACCEPT  # For LiveKit TURN TLS
  sudo iptables -I INPUT 1 -p tcp --dport 7881 -j ACCEPT  # For LiveKit RTC TCP
  sudo iptables -I INPUT 1 -p udp --dport 3478 -j ACCEPT  # For LiveKit TURN UDP
  sudo iptables -I INPUT 1 -p udp --dport 50000:60000 -j ACCEPT # For LiveKit RTC UDP
  sudo iptables -I INPUT 1 -p udp --dport 5060 -j ACCEPT  # For LiveKit SIP UDP
  sudo iptables -I INPUT 1 -p udp --dport 10000:20000 -j ACCEPT # For LiveKit SIP RTP
  # Note: Port 7880 is proxied by Nginx locally, so doesn't strictly need an external rule
  ```
- Save the rules:
  ```bash
  sudo netfilter-persistent save
  ```

**7. Install Docker Compose**

- Download the specified version:
  ```bash
  sudo curl -L "[https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname](https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname) -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  ```
- Make it executable:
  ```bash
  sudo chmod 755 /usr/local/bin/docker-compose
  ```
- Verify installation:
  ```bash
  docker-compose --version
  ```

**8. Enable and Start the LiveKit Service**

- Reload systemd:
  ```bash
  sudo systemctl daemon-reload
  ```
- Enable the service:
  ```bash
  sudo systemctl enable livekit-docker
  ```
- Start the service:
  ```bash
  sudo systemctl start livekit-docker
  ```

**9. Verify Installation**

- Check Nginx status:
  ```bash
  sudo systemctl status nginx
  ```
- Check LiveKit service status:
  ```bash
  sudo systemctl status livekit-docker
  ```
- Check Docker container logs (no Caddy container should be present):
  ```bash
  cd /opt/livekit
  sudo /usr/local/bin/docker-compose logs -f
  ```
  (Look for errors in `livekit`, `redis`, `sip`, `egress` logs).
- Test LiveKit functionality using the [LiveKit Example Tools](https://docs.livekit.io/guides/getting-started/example-tools/) or your application, pointing to `wss://<your-livekit-domain.com>` (using the domain configured in Nginx).
- Test TURN functionality specifically (e.g., using the Trickle ICE tool and specifying your TURN server `turn:livekit-turn.example.com:3478` and `turns:livekit-turn.example.com:5349` with temporary credentials if needed).
