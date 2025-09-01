#!/bin/bash

# Production Setup Script for LimeClicks
# This script sets up the production environment on Ubuntu
# It installs pyenv, nvm, Python, Node.js, and all required services

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="limeclicks"
PROJECT_USER="limeclicks"
PROJECT_DIR="/home/${PROJECT_USER}/${PROJECT_NAME}"
PYTHON_VERSION="3.12.0"
NODE_VERSION="20.10.0"
DOMAIN_NAME=""  # Will be set by user input

# Logging
LOG_FILE="/var/log/${PROJECT_NAME}_setup.log"
exec 1> >(tee -a ${LOG_FILE})
exec 2>&1

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
       echo_error "This script must be run as root"
       exit 1
    fi
}

# Update system packages
update_system() {
    echo_info "Updating system packages..."
    apt-get update
    apt-get upgrade -y
    apt-get install -y \
        build-essential \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        wget \
        curl \
        llvm \
        libncurses5-dev \
        libncursesw5-dev \
        xz-utils \
        tk-dev \
        libffi-dev \
        liblzma-dev \
        python3-openssl \
        git \
        nginx \
        redis-server \
        postgresql \
        postgresql-contrib \
        supervisor \
        certbot \
        python3-certbot-nginx \
        ufw \
        fail2ban \
        htop \
        ncdu \
        tree
}

# Create project user
create_project_user() {
    echo_info "Creating project user..."
    if ! id -u ${PROJECT_USER} >/dev/null 2>&1; then
        useradd -m -s /bin/bash ${PROJECT_USER}
        usermod -aG sudo ${PROJECT_USER}
        echo_info "User ${PROJECT_USER} created"
    else
        echo_warning "User ${PROJECT_USER} already exists"
    fi
}

# Install pyenv for the project user
install_pyenv() {
    echo_info "Installing pyenv..."
    sudo -u ${PROJECT_USER} bash <<'EOF'
        if [ ! -d "$HOME/.pyenv" ]; then
            curl https://pyenv.run | bash
            
            # Add to bashrc
            echo '' >> ~/.bashrc
            echo '# Pyenv configuration' >> ~/.bashrc
            echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
            echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
            echo 'eval "$(pyenv init -)"' >> ~/.bashrc
            echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
        fi
EOF
}

# Install Python using pyenv
install_python() {
    echo_info "Installing Python ${PYTHON_VERSION}..."
    sudo -u ${PROJECT_USER} bash <<EOF
        export PYENV_ROOT="/home/${PROJECT_USER}/.pyenv"
        export PATH="\$PYENV_ROOT/bin:\$PATH"
        eval "\$(pyenv init -)"
        
        pyenv install ${PYTHON_VERSION} || echo "Python ${PYTHON_VERSION} already installed"
        pyenv global ${PYTHON_VERSION}
        
        # Upgrade pip
        pip install --upgrade pip setuptools wheel
EOF
}

# Install nvm and Node.js
install_nvm_node() {
    echo_info "Installing NVM and Node.js..."
    sudo -u ${PROJECT_USER} bash <<EOF
        if [ ! -d "\$HOME/.nvm" ]; then
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
            
            # Add to bashrc
            echo '' >> ~/.bashrc
            echo '# NVM configuration' >> ~/.bashrc
            echo 'export NVM_DIR="\$HOME/.nvm"' >> ~/.bashrc
            echo '[ -s "\$NVM_DIR/nvm.sh" ] && \. "\$NVM_DIR/nvm.sh"' >> ~/.bashrc
            echo '[ -s "\$NVM_DIR/bash_completion" ] && \. "\$NVM_DIR/bash_completion"' >> ~/.bashrc
        fi
        
        # Source nvm and install Node
        export NVM_DIR="\$HOME/.nvm"
        [ -s "\$NVM_DIR/nvm.sh" ] && \. "\$NVM_DIR/nvm.sh"
        
        nvm install ${NODE_VERSION}
        nvm use ${NODE_VERSION}
        nvm alias default ${NODE_VERSION}
        
        # Install global packages
        npm install -g pm2 yarn
EOF
}

# Setup PostgreSQL
setup_postgresql() {
    echo_info "Setting up PostgreSQL..."
    
    # Generate secure password
    DB_PASSWORD=$(openssl rand -base64 32)
    
    # Create database and user
    sudo -u postgres psql <<EOF
CREATE USER ${PROJECT_NAME} WITH PASSWORD '${DB_PASSWORD}';
CREATE DATABASE ${PROJECT_NAME}_db OWNER ${PROJECT_NAME};
GRANT ALL PRIVILEGES ON DATABASE ${PROJECT_NAME}_db TO ${PROJECT_NAME};
ALTER USER ${PROJECT_NAME} CREATEDB;
EOF
    
    # Save database credentials
    echo "DB_NAME=${PROJECT_NAME}_db" >> /home/${PROJECT_USER}/.env
    echo "DB_USER=${PROJECT_NAME}" >> /home/${PROJECT_USER}/.env
    echo "DB_PASSWORD=${DB_PASSWORD}" >> /home/${PROJECT_USER}/.env
    echo "DB_HOST=localhost" >> /home/${PROJECT_USER}/.env
    echo "DB_PORT=5432" >> /home/${PROJECT_USER}/.env
    
    chown ${PROJECT_USER}:${PROJECT_USER} /home/${PROJECT_USER}/.env
    chmod 600 /home/${PROJECT_USER}/.env
}

# Clone repository (placeholder - will be done manually initially)
setup_project_directory() {
    echo_info "Setting up project directory..."
    
    if [ ! -d "${PROJECT_DIR}" ]; then
        echo_warning "Project directory not found. Please clone the repository to ${PROJECT_DIR}"
        echo_info "Run: git clone <your-repo-url> ${PROJECT_DIR}"
        echo_info "Then re-run this script with --skip-system flag"
        exit 1
    fi
    
    chown -R ${PROJECT_USER}:${PROJECT_USER} ${PROJECT_DIR}
}

# Install Python dependencies
install_python_dependencies() {
    echo_info "Installing Python dependencies..."
    sudo -u ${PROJECT_USER} bash <<EOF
        cd ${PROJECT_DIR}
        export PYENV_ROOT="/home/${PROJECT_USER}/.pyenv"
        export PATH="\$PYENV_ROOT/bin:\$PATH"
        eval "\$(pyenv init -)"
        
        # Create virtual environment
        python -m venv venv
        source venv/bin/activate
        
        # Install dependencies
        pip install --upgrade pip
        pip install -r requirements.txt
        pip install gunicorn
EOF
}

# Install Node dependencies
install_node_dependencies() {
    echo_info "Installing Node.js dependencies..."
    
    if [ -f "${PROJECT_DIR}/package.json" ]; then
        sudo -u ${PROJECT_USER} bash <<EOF
            cd ${PROJECT_DIR}
            export NVM_DIR="/home/${PROJECT_USER}/.nvm"
            [ -s "\$NVM_DIR/nvm.sh" ] && \. "\$NVM_DIR/nvm.sh"
            
            npm install
            npm run build || echo "No build script found"
EOF
    else
        echo_warning "No package.json found, skipping Node.js dependencies"
    fi
}

# Collect static files
collect_static() {
    echo_info "Collecting static files..."
    sudo -u ${PROJECT_USER} bash <<EOF
        cd ${PROJECT_DIR}
        source venv/bin/activate
        
        python manage.py collectstatic --noinput
        python manage.py migrate --noinput
EOF
}

# Setup systemd services
setup_systemd_services() {
    echo_info "Setting up systemd services..."
    
    # Copy systemd service files
    cp ${PROJECT_DIR}/deploy/systemd/*.service /etc/systemd/system/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable services
    systemctl enable ${PROJECT_NAME}-gunicorn.service
    systemctl enable ${PROJECT_NAME}-celery.service
    systemctl enable ${PROJECT_NAME}-celerybeat.service
    systemctl enable redis.service
    
    # Start services
    systemctl start redis.service
    systemctl start ${PROJECT_NAME}-gunicorn.service
    systemctl start ${PROJECT_NAME}-celery.service
    systemctl start ${PROJECT_NAME}-celerybeat.service
}

# Setup Nginx
setup_nginx() {
    echo_info "Setting up Nginx..."
    
    # Get domain name if not set
    if [ -z "$DOMAIN_NAME" ]; then
        read -p "Enter your domain name (e.g., example.com): " DOMAIN_NAME
    fi
    
    # Copy nginx configuration
    envsubst < ${PROJECT_DIR}/deploy/nginx/limeclicks.conf > /etc/nginx/sites-available/${PROJECT_NAME}
    
    # Enable site
    ln -sf /etc/nginx/sites-available/${PROJECT_NAME} /etc/nginx/sites-enabled/
    
    # Remove default site
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    nginx -t
    
    # Reload nginx
    systemctl reload nginx
}

# Setup SSL with Let's Encrypt
setup_ssl() {
    echo_info "Setting up SSL certificate..."
    
    if [ -n "$DOMAIN_NAME" ]; then
        certbot --nginx -d ${DOMAIN_NAME} -d www.${DOMAIN_NAME} --non-interactive --agree-tos --email admin@${DOMAIN_NAME}
    else
        echo_warning "Domain name not set, skipping SSL setup"
    fi
}

# Setup firewall
setup_firewall() {
    echo_info "Setting up firewall..."
    
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 'Nginx Full'
    ufw --force enable
}

# Setup monitoring
setup_monitoring() {
    echo_info "Setting up monitoring..."
    
    # Create monitoring script
    cat > /usr/local/bin/${PROJECT_NAME}-health-check.sh <<'EOF'
#!/bin/bash
# Health check script

check_service() {
    if systemctl is-active --quiet $1; then
        echo "$1 is running"
    else
        echo "$1 is not running, attempting restart..."
        systemctl restart $1
        
        # Send notification (implement your notification method)
        # echo "Service $1 was down and has been restarted" | mail -s "Service Alert" admin@example.com
    fi
}

# Check all services
check_service "limeclicks-gunicorn"
check_service "limeclicks-celery"
check_service "limeclicks-celerybeat"
check_service "redis"
check_service "nginx"
EOF
    
    chmod +x /usr/local/bin/${PROJECT_NAME}-health-check.sh
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/${PROJECT_NAME}-health-check.sh") | crontab -
}

# Create update script
create_update_script() {
    echo_info "Creating update script..."
    
    cat > /usr/local/bin/${PROJECT_NAME}-update.sh <<'EOF'
#!/bin/bash
# Update script for deployments

set -e

PROJECT_DIR="/home/limeclicks/limeclicks"
PROJECT_USER="limeclicks"

echo "Starting deployment update..."

# Pull latest code
sudo -u ${PROJECT_USER} bash -c "cd ${PROJECT_DIR} && git pull origin main"

# Install/update Python dependencies
sudo -u ${PROJECT_USER} bash -c "cd ${PROJECT_DIR} && source venv/bin/activate && pip install -r requirements.txt"

# Run migrations
sudo -u ${PROJECT_USER} bash -c "cd ${PROJECT_DIR} && source venv/bin/activate && python manage.py migrate --noinput"

# Collect static files
sudo -u ${PROJECT_USER} bash -c "cd ${PROJECT_DIR} && source venv/bin/activate && python manage.py collectstatic --noinput"

# Restart services
systemctl restart limeclicks-gunicorn
systemctl restart limeclicks-celery
systemctl restart limeclicks-celerybeat

echo "Deployment update completed!"
EOF
    
    chmod +x /usr/local/bin/${PROJECT_NAME}-update.sh
}

# Main installation flow
main() {
    echo_info "Starting LimeClicks production setup..."
    
    # Parse arguments
    SKIP_SYSTEM=false
    for arg in "$@"; do
        case $arg in
            --skip-system)
                SKIP_SYSTEM=true
                shift
                ;;
            --domain=*)
                DOMAIN_NAME="${arg#*=}"
                shift
                ;;
        esac
    done
    
    check_root
    
    if [ "$SKIP_SYSTEM" = false ]; then
        update_system
        create_project_user
        install_pyenv
        install_python
        install_nvm_node
        setup_postgresql
    fi
    
    setup_project_directory
    install_python_dependencies
    install_node_dependencies
    collect_static
    setup_systemd_services
    setup_nginx
    setup_ssl
    setup_firewall
    setup_monitoring
    create_update_script
    
    echo_info "=========================================="
    echo_info "LimeClicks production setup completed!"
    echo_info "=========================================="
    echo_info ""
    echo_info "Important information:"
    echo_info "- Project user: ${PROJECT_USER}"
    echo_info "- Project directory: ${PROJECT_DIR}"
    echo_info "- Environment file: /home/${PROJECT_USER}/.env"
    echo_info "- Update script: /usr/local/bin/${PROJECT_NAME}-update.sh"
    echo_info ""
    echo_info "Services status:"
    systemctl status ${PROJECT_NAME}-gunicorn --no-pager
    systemctl status ${PROJECT_NAME}-celery --no-pager
    systemctl status ${PROJECT_NAME}-celerybeat --no-pager
    echo_info ""
    echo_info "Next steps:"
    echo_info "1. Review and update /home/${PROJECT_USER}/.env with your settings"
    echo_info "2. Set up your domain DNS to point to this server"
    echo_info "3. Run: certbot --nginx (if SSL setup was skipped)"
    echo_info "4. Set up GitHub Actions for CI/CD"
}

# Run main function
main "$@"