# Cloudflare Origin Certificate Setup Guide

This guide covers setting up SSL/TLS using Cloudflare Origin Certificates instead of Let's Encrypt, which is the recommended approach when using Cloudflare as your CDN/proxy.

## Table of Contents
- [Overview](#overview)
- [Benefits of Cloudflare Origin Certificates](#benefits)
- [Generate Origin Certificate](#generate-origin-certificate)
- [Server Configuration](#server-configuration)
- [Nginx SSL Configuration](#nginx-ssl-configuration)
- [Cloudflare SSL Settings](#cloudflare-ssl-settings)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## Overview

Cloudflare Origin Certificates are free SSL certificates that encrypt traffic between Cloudflare and your origin server. They're only valid when used with Cloudflare's proxy (orange cloud).

## Benefits

1. **15-year validity** (vs 90 days for Let's Encrypt)
2. **No renewal needed** for up to 15 years
3. **Automatic trust** by Cloudflare
4. **Simpler setup** - no ACME challenges
5. **Works seamlessly** with Cloudflare's proxy
6. **Wildcard support** included

## Generate Origin Certificate

### Method 1: Via Cloudflare Dashboard (Recommended)

1. Log into Cloudflare Dashboard
2. Select your domain
3. Go to **SSL/TLS** → **Origin Server**
4. Click **Create Certificate**
5. Choose:
   - **Private key type**: RSA (2048) or ECDSA
   - **Hostnames**: 
     - `yourdomain.com`
     - `*.yourdomain.com` (wildcard)
     - `sse.yourdomain.com` (if using SSE subdomain)
   - **Certificate Validity**: 15 years (recommended)
6. Click **Create**
7. **SAVE BOTH**:
   - Origin Certificate
   - Private Key (won't be shown again!)

### Method 2: Via Cloudflare API

```bash
# Generate certificate via API
curl -X POST "https://api.cloudflare.com/client/v4/certificates" \
     -H "X-Auth-Email: your-email@example.com" \
     -H "X-Auth-Key: your-global-api-key" \
     -H "Content-Type: application/json" \
     --data '{
       "hostnames": ["yourdomain.com", "*.yourdomain.com"],
       "requested_validity": 5475,
       "request_type": "origin-rsa",
       "csr": ""
     }'
```

## Server Configuration

### 1. Create SSL Directory

```bash
# Create directory for certificates
sudo mkdir -p /etc/ssl/cloudflare
sudo chmod 700 /etc/ssl/cloudflare
```

### 2. Save Certificates

```bash
# Save the origin certificate
sudo nano /etc/ssl/cloudflare/cert.pem
# Paste the certificate content and save

# Save the private key
sudo nano /etc/ssl/cloudflare/key.pem
# Paste the private key content and save

# Set proper permissions
sudo chmod 600 /etc/ssl/cloudflare/key.pem
sudo chmod 644 /etc/ssl/cloudflare/cert.pem
sudo chown root:root /etc/ssl/cloudflare/*
```

### 3. Download Cloudflare Origin CA Root Certificate

```bash
# Download Cloudflare's root certificate (for origin pull verification)
sudo wget -O /etc/ssl/cloudflare/cloudflare_origin_rsa.pem https://developers.cloudflare.com/ssl/static/origin_ca_rsa_root.pem

# For ECDSA (if you chose ECDSA key type)
sudo wget -O /etc/ssl/cloudflare/cloudflare_origin_ecc.pem https://developers.cloudflare.com/ssl/static/origin_ca_ecc_root.pem
```

## Nginx SSL Configuration

### Update Nginx Configuration

Edit `/etc/nginx/sites-available/limeclicks`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS (Cloudflare will handle this, but good as backup)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # Cloudflare Origin Certificate
    ssl_certificate /etc/ssl/cloudflare/cert.pem;
    ssl_certificate_key /etc/ssl/cloudflare/key.pem;
    
    # SSL configuration optimized for Cloudflare
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    
    # SSL session caching
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;
    
    # Cloudflare Authenticated Origin Pulls (optional but recommended)
    # This ensures only Cloudflare can connect to your origin
    ssl_client_certificate /etc/ssl/cloudflare/cloudflare_origin_rsa.pem;
    ssl_verify_client on;
    
    # Cloudflare real IP configuration
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 131.0.72.0/22;
    
    # IPv6
    set_real_ip_from 2400:cb00::/32;
    set_real_ip_from 2606:4700::/32;
    set_real_ip_from 2803:f800::/32;
    set_real_ip_from 2405:b500::/32;
    set_real_ip_from 2405:8100::/32;
    set_real_ip_from 2a06:98c0::/29;
    set_real_ip_from 2c0f:f248::/32;
    
    real_ip_header CF-Connecting-IP;
    
    # Your application configuration
    location / {
        proxy_pass http://limeclicks_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Static files
    location /static/ {
        alias /home/limeclicks/limeclicks/staticfiles/;
        expires 30d;
    }
    
    location /media/ {
        alias /home/limeclicks/limeclicks/media/;
        expires 7d;
    }
}
```

### Test and Reload Nginx

```bash
# Test configuration
sudo nginx -t

# If successful, reload
sudo systemctl reload nginx
```

## Cloudflare SSL Settings

### 1. SSL/TLS Encryption Mode

In Cloudflare Dashboard:
1. Go to **SSL/TLS** → **Overview**
2. Set encryption mode to **Full (strict)**
   - This requires a valid certificate on origin (which we now have)
   - Provides end-to-end encryption

### 2. Enable Authenticated Origin Pulls

1. Go to **SSL/TLS** → **Origin Server**
2. Enable **Authenticated Origin Pulls**
3. This ensures only Cloudflare can connect to your origin

### 3. Minimum TLS Version

1. Go to **SSL/TLS** → **Edge Certificates**
2. Set **Minimum TLS Version** to 1.2

### 4. Always Use HTTPS

1. Go to **SSL/TLS** → **Edge Certificates**
2. Enable **Always Use HTTPS**

### 5. HTTP Strict Transport Security (HSTS)

1. Go to **SSL/TLS** → **Edge Certificates**
2. Enable HSTS with:
   - Max Age: 6 months (recommended)
   - Include subdomains: Yes
   - Preload: Yes (after testing)
   - No-Sniff Header: Yes

## Update Setup Script

Update the `deploy/setup_production.sh` script to use Cloudflare certificates:

```bash
# Replace the setup_ssl function with:
setup_ssl() {
    echo_info "Setting up Cloudflare Origin SSL certificate..."
    
    # Create SSL directory
    mkdir -p /etc/ssl/cloudflare
    chmod 700 /etc/ssl/cloudflare
    
    # Download Cloudflare Origin CA root certificate
    wget -O /etc/ssl/cloudflare/cloudflare_origin_rsa.pem \
        https://developers.cloudflare.com/ssl/static/origin_ca_rsa_root.pem
    
    echo_warning "Please add your Cloudflare Origin Certificate:"
    echo_info "1. Generate certificate at: https://dash.cloudflare.com/ssl-tls/origin-server"
    echo_info "2. Save certificate to: /etc/ssl/cloudflare/cert.pem"
    echo_info "3. Save private key to: /etc/ssl/cloudflare/key.pem"
    echo_info "4. Run: chmod 600 /etc/ssl/cloudflare/key.pem"
    echo_info "5. Run: chmod 644 /etc/ssl/cloudflare/cert.pem"
}
```

## Automated Certificate Installation

Create a script to automate certificate installation:

```bash
#!/bin/bash
# File: deploy/install_cloudflare_cert.sh

set -e

echo "Cloudflare Origin Certificate Installation"
echo "=========================================="
echo ""
echo "Please have your certificate and private key ready."
echo ""

# Create directory
sudo mkdir -p /etc/ssl/cloudflare
sudo chmod 700 /etc/ssl/cloudflare

# Create certificate file
echo "Paste your Cloudflare Origin Certificate below (Ctrl+D when done):"
sudo tee /etc/ssl/cloudflare/cert.pem > /dev/null

echo ""
echo "Paste your Private Key below (Ctrl+D when done):"
sudo tee /etc/ssl/cloudflare/key.pem > /dev/null

# Set permissions
sudo chmod 600 /etc/ssl/cloudflare/key.pem
sudo chmod 644 /etc/ssl/cloudflare/cert.pem
sudo chown root:root /etc/ssl/cloudflare/*

# Download Cloudflare root certificate
echo "Downloading Cloudflare root certificate..."
sudo wget -q -O /etc/ssl/cloudflare/cloudflare_origin_rsa.pem \
    https://developers.cloudflare.com/ssl/static/origin_ca_rsa_root.pem

echo "Certificate installation complete!"

# Test Nginx configuration
echo "Testing Nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "Nginx configuration is valid. Reloading..."
    sudo systemctl reload nginx
    echo "SSL setup complete!"
else
    echo "Nginx configuration has errors. Please fix and reload manually."
fi
```

## Verification

### 1. Test SSL Configuration

```bash
# Test locally (will fail certificate validation since it's Cloudflare-only)
curl -I https://yourdomain.com --resolve yourdomain.com:443:your-server-ip

# Test through Cloudflare (should work)
curl -I https://yourdomain.com
```

### 2. Check SSL Status in Cloudflare

1. Go to **SSL/TLS** → **Overview**
2. Should show "Your SSL/TLS encryption mode is Full (strict)"

### 3. Use SSL Checker

Visit: https://www.sslshopper.com/ssl-checker.html
- Should show certificate issued by Cloudflare

## Troubleshooting

### Common Issues

#### 1. 525 SSL Handshake Failed
- **Cause**: Origin certificate not properly installed
- **Fix**: Verify certificate and key files are correct

#### 2. 526 Invalid SSL Certificate
- **Cause**: Using self-signed certificate with Full (strict) mode
- **Fix**: Use Cloudflare Origin Certificate or switch to Full mode

#### 3. 520 Unknown Error
- **Cause**: Origin server returning empty response
- **Fix**: Check Nginx error logs and application logs

#### 4. Certificate Not Trusted Locally
- **Normal**: Origin certificates are only trusted by Cloudflare
- **Note**: Direct access to origin will show certificate warning

### Debug Commands

```bash
# Check certificate details
openssl x509 -in /etc/ssl/cloudflare/cert.pem -text -noout

# Verify certificate and key match
openssl x509 -noout -modulus -in /etc/ssl/cloudflare/cert.pem | openssl md5
openssl rsa -noout -modulus -in /etc/ssl/cloudflare/key.pem | openssl md5

# Test SSL handshake
openssl s_client -connect localhost:443 -servername yourdomain.com

# Check Nginx SSL configuration
nginx -T 2>&1 | grep -A 10 "ssl_"
```

## Security Best Practices

1. **Always use Full (strict) mode** in Cloudflare
2. **Enable Authenticated Origin Pulls** to prevent direct access
3. **Firewall rules**: Only allow Cloudflare IPs to port 443
4. **Hide origin IP**: Use Cloudflare's proxy for all records
5. **Rate limiting**: Configure in both Cloudflare and Nginx
6. **WAF rules**: Enable Cloudflare's Web Application Firewall

## Firewall Configuration

```bash
# Only allow Cloudflare IPs
for ip in $(curl -s https://www.cloudflare.com/ips-v4); do
    sudo ufw allow from $ip to any port 443
done

for ip in $(curl -s https://www.cloudflare.com/ips-v6); do
    sudo ufw allow from $ip to any port 443
done

# Block direct access
sudo ufw deny 443

# Allow SSH (adjust as needed)
sudo ufw allow 22

# Enable firewall
sudo ufw --force enable
```

## Automatic Updates for Cloudflare IPs

Create a cron job to update Cloudflare IPs:

```bash
# Create update script
cat > /usr/local/bin/update-cloudflare-ips.sh << 'EOF'
#!/bin/bash

# Download latest Cloudflare IPs
CF_IPS_V4=$(curl -s https://www.cloudflare.com/ips-v4)
CF_IPS_V6=$(curl -s https://www.cloudflare.com/ips-v6)

# Update Nginx configuration
cat > /etc/nginx/conf.d/cloudflare-ips.conf << EOL
# Cloudflare IP addresses
# Updated: $(date)

$(echo "$CF_IPS_V4" | sed 's/^/set_real_ip_from /;s/$/;/')
$(echo "$CF_IPS_V6" | sed 's/^/set_real_ip_from /;s/$/;/')

real_ip_header CF-Connecting-IP;
EOL

# Test and reload Nginx
nginx -t && systemctl reload nginx
EOF

chmod +x /usr/local/bin/update-cloudflare-ips.sh

# Add to crontab (weekly update)
(crontab -l 2>/dev/null; echo "0 3 * * 0 /usr/local/bin/update-cloudflare-ips.sh") | crontab -
```

## Summary

Using Cloudflare Origin Certificates provides:
- ✅ No certificate renewal needed for 15 years
- ✅ Perfect integration with Cloudflare
- ✅ Free wildcard certificates
- ✅ Enhanced security with Authenticated Origin Pulls
- ✅ Simplified certificate management
- ✅ Full end-to-end encryption

This setup ensures your traffic is encrypted from visitor to Cloudflare and from Cloudflare to your origin server.