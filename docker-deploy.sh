#!/bin/bash

# Script de Deploy Automatizado para Sistema DVR com Docker
# Debian Bookworm

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para log
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Verificar se está rodando como root
if [[ $EUID -eq 0 ]]; then
   error "Este script não deve ser executado como root"
fi

# Verificar se Docker está instalado
check_docker() {
    log "Verificando instalação do Docker..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker não está instalado. Execute o script de instalação primeiro."
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose não está instalado. Execute o script de instalação primeiro."
    fi
    
    # Verificar se usuário está no grupo docker
    if ! groups $USER | grep -q docker; then
        warn "Usuário não está no grupo docker. Adicionando..."
        sudo usermod -aG docker $USER
        log "Por favor, faça logout e login novamente, ou execute: newgrp docker"
        exit 1
    fi
    
    log "Docker está instalado e configurado corretamente"
}

# Configurar variáveis de ambiente
setup_env() {
    log "Configurando variáveis de ambiente..."
    
    if [ ! -f .env ]; then
        if [ -f env.example ]; then
            cp env.example .env
            log "Arquivo .env criado a partir do exemplo"
        else
            error "Arquivo env.example não encontrado"
        fi
    else
        warn "Arquivo .env já existe"
    fi
    
    # Gerar SECRET_KEY se não estiver definida
    if grep -q "sua-chave-secreta-muito-segura-aqui" .env; then
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
        sed -i "s/sua-chave-secreta-muito-segura-aqui-mude-isto/$SECRET_KEY/" .env
        log "SECRET_KEY gerada automaticamente"
    fi
    
    # Configurar ALLOWED_HOSTS
    IP_ADDRESS=$(hostname -I | awk '{print $1}')
    sed -i "s/seu-ip-aqui/$IP_ADDRESS/" .env
    log "ALLOWED_HOSTS configurado com IP: $IP_ADDRESS"
}

# Criar diretórios necessários
create_directories() {
    log "Criando diretórios necessários..."
    
    mkdir -p recordings media staticfiles logs backups ssl monitoring
    
    # Definir permissões
    sudo chown -R $USER:$USER recordings media staticfiles logs backups
    chmod 755 recordings media staticfiles logs backups
    chmod 700 ssl
    
    log "Diretórios criados com permissões corretas"
}

# Configurar monitoramento
setup_monitoring() {
    log "Configurando monitoramento..."
    
    cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'dvr-system'
    static_configs:
      - targets: ['web:8000']
    metrics_path: '/metrics/'
    
  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:80']
    metrics_path: '/nginx_status'
    
  - job_name: 'postgres'
    static_configs:
      - targets: ['db:5432']
    metrics_path: '/metrics'
EOF
    
    log "Configuração do Prometheus criada"
}

# Backup do sistema atual
backup_existing() {
    if [ -d recordings ] && [ "$(ls -A recordings)" ]; then
        log "Fazendo backup do sistema atual..."
        BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S)"
        tar -czf "backups/${BACKUP_NAME}.tar.gz" recordings/ media/ staticfiles/ 2>/dev/null || true
        log "Backup salvo em: backups/${BACKUP_NAME}.tar.gz"
    fi
}

# Parar serviços existentes
stop_existing() {
    log "Parando serviços existentes..."
    docker-compose down 2>/dev/null || true
    docker system prune -f 2>/dev/null || true
}

# Construir e iniciar serviços
build_and_start() {
    log "Construindo imagens Docker..."
    docker-compose build --no-cache
    
    log "Iniciando serviços..."
    docker-compose up -d
    
    # Aguardar serviços ficarem prontos
    log "Aguardando serviços ficarem prontos..."
    sleep 30
    
    # Verificar se os serviços estão rodando
    if ! docker-compose ps | grep -q "Up"; then
        error "Falha ao iniciar os serviços"
    fi
    
    log "Serviços iniciados com sucesso"
}

# Executar migrações e setup inicial
setup_database() {
    log "Executando migrações do banco de dados..."
    docker-compose exec -T web python manage.py migrate
    
    log "Coletando arquivos estáticos..."
    docker-compose exec -T web python manage.py collectstatic --noinput
    
    # Verificar se superusuário existe
    if ! docker-compose exec -T web python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).exists())" 2>/dev/null | grep -q "True"; then
        log "Criando superusuário..."
        echo "Por favor, crie um superusuário:"
        docker-compose exec web python manage.py createsuperuser
    else
        log "Superusuário já existe"
    fi
}

# Configurar SSL (opcional)
setup_ssl() {
    read -p "Deseja configurar SSL/HTTPS? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "Configurando SSL..."
        
        read -p "Digite o domínio (ex: dvr.exemplo.com): " DOMAIN
        
        if [ -n "$DOMAIN" ]; then
            # Instalar certbot se não estiver instalado
            if ! command -v certbot &> /dev/null; then
                log "Instalando Certbot..."
                sudo apt update
                sudo apt install -y certbot
            fi
            
            # Obter certificado
            log "Obtendo certificado SSL para $DOMAIN..."
            sudo certbot certonly --standalone -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
            
            # Copiar certificados
            sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/
            sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/
            sudo chown $USER:$USER ssl/*
            
            # Atualizar nginx.conf
            sed -i "s/localhost/$DOMAIN/g" nginx.conf
            sed -i 's/# server {/server {/g' nginx.conf
            sed -i 's/#     listen 443/    listen 443/g' nginx.conf
            sed -i 's/#     server_name/    server_name/g' nginx.conf
            sed -i 's/#     ssl_certificate/    ssl_certificate/g' nginx.conf
            sed -i 's/#     ssl_certificate_key/    ssl_certificate_key/g' nginx.conf
            sed -i 's/#     ssl_protocols/    ssl_protocols/g' nginx.conf
            sed -i 's/#     ssl_ciphers/    ssl_ciphers/g' nginx.conf
            sed -i 's/#     ssl_prefer_server_ciphers/    ssl_prefer_server_ciphers/g' nginx.conf
            sed -i 's/#     ssl_session_cache/    ssl_session_cache/g' nginx.conf
            sed -i 's/#     ssl_session_timeout/    ssl_session_timeout/g' nginx.conf
            sed -i 's/#     add_header Strict-Transport-Security/    add_header Strict-Transport-Security/g' nginx.conf
            sed -i 's/#     location \/static\//    location \/static\//g' nginx.conf
            sed -i 's/#     location \/media\//    location \/media\//g' nginx.conf
            sed -i 's/#     location \//    location \//g' nginx.conf
            sed -i 's/# }/}/g' nginx.conf
            
            # Reiniciar nginx
            docker-compose restart nginx
            
            log "SSL configurado para $DOMAIN"
        fi
    fi
}

# Configurar firewall
setup_firewall() {
    log "Configurando firewall..."
    
    if command -v ufw &> /dev/null; then
        sudo ufw --force enable
        sudo ufw allow ssh
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        sudo ufw allow 8000/tcp
        log "Firewall configurado"
    else
        warn "UFW não está instalado. Configure o firewall manualmente."
    fi
}

# Configurar backup automático
setup_backup() {
    log "Configurando backup automático..."
    
    cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/$(whoami)/DVR_System/backups"

# Backup do banco de dados
docker-compose exec -T db pg_dump -U dvr_user dvr_system > $BACKUP_DIR/db_$DATE.sql

# Backup das gravações
tar -czf $BACKUP_DIR/recordings_$DATE.tar.gz recordings/ 2>/dev/null || true

# Manter apenas os últimos 7 backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup realizado: $DATE"
EOF
    
    chmod +x backup.sh
    
    # Adicionar ao crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * $(pwd)/backup.sh") | crontab -
    
    log "Backup automático configurado para 2:00 AM diariamente"
}

# Verificar status dos serviços
check_status() {
    log "Verificando status dos serviços..."
    
    echo -e "\n${BLUE}=== Status dos Serviços ===${NC}"
    docker-compose ps
    
    echo -e "\n${BLUE}=== Logs dos Serviços ===${NC}"
    docker-compose logs --tail=10 web
    
    echo -e "\n${BLUE}=== URLs de Acesso ===${NC}"
    echo "Dashboard: http://$(hostname -I | awk '{print $1}'):8000"
    echo "Admin: http://$(hostname -I | awk '{print $1}'):8000/admin/"
    echo "Grafana: http://$(hostname -I | awk '{print $1}'):3000"
    echo "Prometheus: http://$(hostname -I | awk '{print $1}'):9090"
}

# Função principal
main() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Deploy Sistema DVR - Docker  ${NC}"
    echo -e "${BLUE}================================${NC}"
    
    check_docker
    setup_env
    create_directories
    setup_monitoring
    backup_existing
    stop_existing
    build_and_start
    setup_database
    setup_ssl
    setup_firewall
    setup_backup
    check_status
    
    echo -e "\n${GREEN}================================${NC}"
    echo -e "${GREEN}  Deploy concluído com sucesso!  ${NC}"
    echo -e "${GREEN}================================${NC}"
    echo -e "\n${YELLOW}Próximos passos:${NC}"
    echo "1. Acesse o dashboard: http://$(hostname -I | awk '{print $1}'):8000"
    echo "2. Faça login com o superusuário criado"
    echo "3. Adicione suas câmeras IP"
    echo "4. Configure as gravações"
    echo -e "\n${YELLOW}Comandos úteis:${NC}"
    echo "docker-compose ps          # Ver status"
    echo "docker-compose logs -f     # Ver logs"
    echo "docker-compose down        # Parar serviços"
    echo "docker-compose up -d       # Iniciar serviços"
}

# Executar função principal
main "$@" 