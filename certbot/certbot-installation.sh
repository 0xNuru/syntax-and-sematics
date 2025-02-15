# Error occurs if:
# DNS hasn't fully propagated yet
#	'dig api.example.com +short"
# EC2 security group/firewall is blocking access 
#  	Add inbound rules:
#	HTTP (port 80) from 0.0.0.0/0
#	HTTPS (port 443) from 0.0.0.0/0
# The EC2 instance is not accessible from the internet
#	curl -v http://api.example.com


sudo certbot --nginx -d api.example.com

# Follow the prompts from Certbot. It will automatically modify your Nginx configuration to use HTTPS.

# Setup auto renewal with cron job
sudo crontab -e

# Add this line
0 3 * * * certbot renew --quiet
