# README: Manual Caddy Setup for LiveKit

## Overview

This guide provides instructions for setting up the Caddy web server manually (without Docker) to act as a reverse proxy for a LiveKit installation (`livekit-server`). It covers two primary scenarios:

1.  **Shared Caddy Server (Application Layer - L7):** You are running Caddy on a server that _also_ hosts other standard websites or applications using HTTPS on port 443. This method uses the standard Caddy binary and a `Caddyfile`. (**Recommended for most shared environments**).
2.  **Dedicated Caddy Server (Layer 4 - L4):** Caddy is primarily dedicated to proxying LiveKit, or any other applications running on the server do not conflict with Caddy using port 443 for raw TLS/TCP proxying via the `layer4` app. This method requires a **custom Caddy build** and uses a YAML configuration file.

Choose the approach below that best fits your server's configuration.

## Prerequisites (Common to Both Approaches)

- A server (e.g., Linux, nb: I'm using ubuntu 24) with root or `sudo` access.
- LiveKit server (`livekit-server`) installed and running (typically listening on `localhost:7880`).
- A TURN server configured and accessible (e.g., listening for TLS connections on `xx.xx.xx.xx:5349`).
- Your domain names (e.g., `livekit.xxx.im` for the API/WebSocket and `livekit-turn.xxx.im` for TURN) correctly pointing via DNS A records to your Caddy server's public IP address.
- Firewall rules allowing traffic on ports 80 (for HTTP ACME challenges) and 443 (for HTTPS/TLS).

---

## Approach 1: Caddyfile Method (Application Layer - L7)

This approach is best when your Caddy instance needs to serve both LiveKit **and** other standard HTTPS websites/applications on the same server using port 443.

**Concept:**

- Leverages Caddy's standard `http` app, which listens on ports 80 and 443.
- The `http` app automatically handles TLS certificates (via Let's Encrypt or other ACME CAs) and uses Server Name Indication (SNI) to route incoming requests to the correct site block based on the requested domain name.
- LiveKit API/WebSocket traffic is handled by a standard `reverse_proxy`.
- LiveKit TURN-over-TLS traffic is handled using `reverse_proxy` configured specifically for TLS passthrough/termination and proxying to the TURN backend.
- **No custom Caddy build is required.** Uses the standard Caddy binary.

**Steps:**

### 1. Install Standard Caddy

If Caddy isn't installed, follow the official instructions for your OS. For Debian/Ubuntu:

```bash
# Update package lists and install prerequisites
sudo apt update
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https

# Add Caddy repository GPG key
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg

# Add Caddy repository
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list

# Update package lists again and install Caddy
sudo apt update
sudo apt install caddy
```

This installs the standard Caddy binary and usually sets it up as a systemd service.

### 2. Prepare Configuration Directories

Caddy needs directories for storing certificates and state (/data is used in examples, adjust if needed) and for logs.

```bash
# Create directories
sudo mkdir -p /data /var/log/caddy

# Set ownership to the user Caddy runs as (usually 'caddy' for the systemd service)
sudo chown -R caddy:caddy /data /var/log/caddy
```

### 3. Create the Merged Caddyfile

Create or edit Caddy's main configuration file at /etc/caddy/Caddyfile. Add the global options and site blocks for LiveKit, alongside any other sites you need to serve.

````caddyfile
# /etc/caddy/Caddyfile

# Global Options Block
{
	# IMPORTANT: Replace with your email for ACME TLS certificates
	email 0xnuru@example.com

	# Optional: Uncomment for Let's Encrypt staging environment during testing so tht you don't hit eff.org's rate limit
	# acme_ca https://acme-staging-v02.api.letsencrypt.org/directory

	# Logging configuration
	log {
		output file /var/log/caddy/caddy.log {
			roll_size 100mb # Max size before rotating
			roll_keep 10    # Number of rotated files to keep
		}
		level INFO # Log levels: DEBUG, INFO, WARN, ERROR
		format console # Other formats: json
	}

	# Storage configuration (uses /data for certs, etc.)
	storage file_system {
		root /data
	}
}

# --- LiveKit Site Blocks ---

# LiveKit API/Service (WebSockets, API calls)
livekit.outbound.im { # Replace with your actual LiveKit domain
	# Standard reverse proxy to the LiveKit service running locally
	# Caddy handles TLS termination and proxies HTTP/WebSocket traffic.
	reverse_proxy localhost:7880
}

# LiveKit TURN Service (Handles TURN over TLS)
livekit-turn.outbound.im { # Replace with your actual TURN domain
	# Reverse proxy the raw TLS connection to the upstream TURN server.
	# Caddy terminates the client TLS, then initiates a new TLS connection to the upstream.
	reverse_proxy xx.xx.xx.xx:5349 { # Replace with your TURN server IP & TLS Port
		# Configure the transport layer for the connection TO the upstream
		transport http { # Use 'http' transport block for generic TCP/TLS settings
			# Enable TLS for the connection to the upstream TURN server
			tls
			# Optional: Uncomment if your upstream TURN server uses a
			# self-signed or otherwise untrusted TLS certificate.
			# tls_insecure_skip_verify
		}
	}
}


# --- Add Your Other Site Blocks Below ---

# Example: A standard website hosted by Caddy
# www.myothersite.com, myothersite.com {
#	  root * /var/www/myothersite
#	  file_server
#	  encode gzip
# }

# Example: An API backend running on another port
# api.myothersite.com {
#    reverse_proxy localhost:8080
# }


### 4. Validate and Run Caddy

Validate: Check your Caddyfile syntax:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
````

Run/Reload: If validation passes, apply the configuration by reloading the Caddy service:

```bash
sudo systemctl reload caddy
```

Or, if Caddy wasn't running or you prefer restarting:

```bash
sudo systemctl restart caddy
```

Check Status: Verify the service is running:

```bash
sudo systemctl status caddy
```

Check Logs: Monitor logs for activity or errors:

```bash
sudo journalctl -u caddy -f --lines 100
```

## Approach 2: Layer4/YAML Method (Dedicated Caddy / No L7 Port Conflict)

This approach uses a custom Caddy build with specific plugins (caddy-l4, caddy-yaml) and a YAML configuration file. It's suitable only if Caddy is not required to serve standard HTTPS websites on port 443, allowing the layer4 app to bind directly to that port for LiveKit's TLS traffic.

**Concept:**

- Uses a custom Caddy build including caddy-l4 (for Layer 4 proxying) and caddy-yaml (to read YAML configs).
- Configuration is defined in a YAML file (e.g., livekit.yaml).
- The layer4 app listens directly on port 443, inspects the TLS SNI, and proxies the raw TCP/TLS stream to the appropriate backend (LiveKit or TURN).
- This will conflict if Caddy's standard http app (configured via Caddyfile or JSON) also tries to bind to port 443 for other sites.

**Steps:**

### 1. Install Go Programming Language

xcaddy (used to build Caddy) requires Go. Install it if you haven't already. Instructions vary by OS. On Debian/Ubuntu, you might use apt (check for recent enough versions) or download from the official Go website (https://go.dev/doc/install).

```bash
# Example using apt (may not be the latest version)
sudo apt update
sudo apt install golang-go

# Verify installation
go version
```

### 2. Install xcaddy

Use go to install xcaddy:

```bash
# Ensure Go environment variables ($GOPATH, $GOBIN) are set correctly
go install github.com/caddyserver/xcaddy/cmd/xcaddy@latest
```

This usually installs xcaddy to $GOPATH/bin/xcaddy (often ~/go/bin/xcaddy). Ensure this directory is in your system's $PATH or use the full path to the binary in the next step.

### 3. Build Custom Caddy

Use xcaddy to build Caddy with the required plugins:

```bash
# Navigate to a temporary directory or where you want the binary built
# Ensure $GOPATH/bin is in your $PATH or use the full path like ~/go/bin/xcaddy
~/go/bin/xcaddy build \
    --with github.com/abiosoft/caddy-yaml \
    --with github.com/mholt/caddy-l4
```

This creates a custom caddy binary in the current directory.

### 4. Replace Standard Caddy Binary (If using systemd service)

To use this custom build with the standard systemd service, replace the existing Caddy binary:

```bash
# Backup the original binary first (important!)
sudo mv /usr/bin/caddy /usr/bin/caddy.standard

# Move the custom-built binary into place
sudo mv ./caddy /usr/bin/caddy
sudo chmod +x /usr/bin/caddy

# Verify the new binary has the required modules (look for l4 and yaml)
caddy list-modules | egrep 'layer4|yaml'
```

### 5. Prepare Configuration Directories

Ensure the directories for Caddy's state/certificates (/data) and logs (/var/log/caddy) exist and have correct permissions (same as Step 2 in Approach 1).

```bash
# Create directories if they don't exist
sudo mkdir -p /data /var/log/caddy

# Set ownership (assuming 'caddy' user for the systemd service)
sudo chown -R caddy:caddy /data /var/log/caddy
```

### 6. Create livekit.yaml

Create the YAML configuration file, typically at /etc/caddy/livekit.yaml.

```yaml
# /etc/caddy/livekit.yaml
nuru@telex:/etc/caddy$ cat livekit.yaml
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
        - livekit.outbound.im
        - livekit-turn.outbound.im
  layer4:
    servers:
      main:
        listen: [":443"]
        routes:
          - match:
              - tls:
                  sni:
                    - "livekit-turn.outbound.im"
            handle:
              - handler: tls
              - handler: proxy
                upstreams:
                  - dial: ["95.217.195.23:5349"]
          - match:
              - tls:
                  sni:
                    - "livekit.outbound.im"
            handle:
              - handler: tls
                connection_policies:
                  - alpn: ["http/1.1"]
              - handler: proxy
                upstreams:
                  - dial: ["localhost:7880"]
```

Important: If a /etc/caddy/Caddyfile exists, Caddy might prefer it by default. Rename or remove /etc/caddy/Caddyfile to ensure livekit.yaml is used, or explicitly tell Caddy which file to use when running/configuring the service.

### 7. Configure and Run Caddy Service

Ensure the Caddy service uses the YAML file.

Option A (Simple): Rename or remove /etc/caddy/Caddyfile. Caddy v2 often automatically detects caddy.json or caddy.yaml in /etc/caddy/ if Caddyfile is absent. Check your systemd unit file (/lib/systemd/system/caddy.service or similar) doesn't force --config /etc/caddy/Caddyfile.

Option B (Explicit): Modify the Caddy systemd service unit file to explicitly use the YAML config.

```bash
# Create a systemd override file
sudo systemctl edit caddy
```

Add these lines to the editor:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/caddy run --config /etc/caddy/livekit.yaml --adapter yaml
```

Save and exit. Then reload systemd and restart Caddy:

```bash
sudo systemctl daemon-reload
sudo systemctl restart caddy

# Check status and logs
sudo systemctl status caddy
sudo journalctl -u caddy -f --lines 100
```

If you encounter any issues, check that you've removed or renamed any existing /etc/caddy/Caddyfile, and that port 443 isn't already in use by another service.
