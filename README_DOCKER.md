# Sistema DVR - Deploy com Docker no Debian Bookworm

Este guia explica como fazer o deploy do Sistema DVR usando Docker no Debian Bookworm.

## 📋 Pré-requisitos

### Sistema Operacional
- Debian Bookworm (12.x)
- Docker Engine 24.x+
- Docker Compose 2.x+

### Recursos Mínimos
- **CPU**: 2 cores
- **RAM**: 4GB
- **Armazenamento**: 50GB (SSD recomendado)
- **Rede**: Conexão estável com internet

## 🐳 Instalação do Docker

### 1. Atualizar o sistema
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Instalar dependências
```bash
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common
```

### 3. Adicionar repositório oficial do Docker
```bash
# Adicionar chave GPG
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Adicionar repositório
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### 4. Instalar Docker Engine
```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 5. Adicionar usuário ao grupo docker
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 6. Verificar instalação
```bash
docker --version
docker compose version
```

## 🚀 Deploy do Sistema DVR

### 1. Clonar o repositório
```bash
git clone <url-do-repositorio>
cd DVR_System
```

### 2. Configurar variáveis de ambiente
```bash
cp .env.example .env
nano .env
```

Exemplo de configuração `.env`:
```env
# Django
SECRET_KEY=sua-chave-secreta-muito-segura-aqui
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,seu-ip-aqui

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=dvr_system
DB_USER=dvr_user
DB_PASSWORD=sua-senha-segura
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# DVR Settings
RECORDINGS_PATH=/app/recordings
MAX_RECORDING_DAYS=30
MOTION_DETECTION_SENSITIVITY=0.3
RECORDING_DURATION=30
MOTION_TIMEOUT=4
MOTION_START_DELAY=10
FRAME_RATE=15

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-de-app
```

### 3. Criar diretórios necessários
```bash
mkdir -p recordings media staticfiles logs
sudo chown -R 1000:1000 recordings media staticfiles logs
```

### 4. Construir e iniciar os containers
```bash
# Construir imagens
docker compose build

# Iniciar serviços
docker compose up -d
```

### 5. Executar migrações
```bash
docker compose exec web python manage.py migrate
```

### 6. Criar superusuário
```bash
docker compose exec web python manage.py createsuperuser
```

### 7. Coletar arquivos estáticos
```bash
docker compose exec web python manage.py collectstatic --noinput
```

## 📁 Estrutura de Arquivos Docker

```
DVR_System/
├── docker-compose.yml          # Configuração dos serviços
├── Dockerfile                  # Imagem do Django
├── Dockerfile.nginx            # Imagem do Nginx
├── nginx.conf                  # Configuração do Nginx
├── .env                        # Variáveis de ambiente
├── .env.example               # Exemplo de variáveis
├── recordings/                 # Gravações (volume)
├── media/                      # Arquivos de mídia (volume)
├── staticfiles/                # Arquivos estáticos (volume)
└── logs/                       # Logs do sistema (volume)
```

## 🔧 Configuração Avançada

### Configuração de SSL/HTTPS

1. **Obter certificado SSL** (Let's Encrypt):
```bash
sudo apt install certbot
sudo certbot certonly --standalone -d seu-dominio.com
```

2. **Configurar Nginx com SSL**:
```bash
# Copiar certificados para o container
sudo cp /etc/letsencrypt/live/seu-dominio.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/seu-dominio.com/privkey.pem ./ssl/
```

3. **Atualizar docker-compose.yml** para incluir SSL

### Backup Automático

Criar script de backup:
```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/dvr_system"

# Backup do banco de dados
docker compose exec -T db pg_dump -U dvr_user dvr_system > $BACKUP_DIR/db_$DATE.sql

# Backup das gravações
tar -czf $BACKUP_DIR/recordings_$DATE.tar.gz recordings/

# Manter apenas os últimos 7 backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### Monitoramento

Instalar Prometheus e Grafana:
```yaml
# Adicionar ao docker-compose.yml
  prometheus:
    image: prom/prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    ports:
      - "3000:3000"
```

## 🛠️ Comandos Úteis

### Gerenciamento de Containers
```bash
# Ver status dos serviços
docker compose ps

# Ver logs
docker compose logs -f web
docker compose logs -f nginx
docker compose logs -f redis

# Reiniciar serviço
docker compose restart web

# Parar todos os serviços
docker compose down

# Parar e remover volumes
docker compose down -v
```

### Manutenção
```bash
# Backup do banco
docker compose exec db pg_dump -U dvr_user dvr_system > backup.sql

# Restaurar backup
docker compose exec -T db psql -U dvr_user dvr_system < backup.sql

# Limpar gravações antigas
docker compose exec web python manage.py shell -c "
from recordings.tasks import cleanup_old_recordings
cleanup_old_recordings()
"

# Verificar espaço em disco
docker system df
docker volume ls
```

### Atualizações
```bash
# Atualizar código
git pull origin main

# Reconstruir e reiniciar
docker compose down
docker compose build --no-cache
docker compose up -d

# Executar migrações
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

## 🔒 Segurança

### Firewall
```bash
# Configurar UFW
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp  # Apenas se necessário
```

### Configurações de Segurança
```bash
# Desabilitar root login
sudo nano /etc/ssh/sshd_config
# PermitRootLogin no

# Reiniciar SSH
sudo systemctl restart ssh
```

### Backup de Segurança
```bash
# Backup automático diário
sudo crontab -e

# Adicionar linha:
0 2 * * * /path/to/dvr_system/backup.sh
```

## 📊 Monitoramento e Logs

### Logs do Sistema
```bash
# Logs do Django
docker compose logs -f web

# Logs do Nginx
docker compose logs -f nginx

# Logs do Redis
docker compose logs -f redis

# Logs do PostgreSQL
docker compose logs -f db
```

### Métricas de Performance
```bash
# Uso de CPU e RAM
docker stats

# Espaço em disco
df -h
du -sh recordings/

# Conexões ativas
docker compose exec web netstat -an | grep :8000
```

## 🚨 Troubleshooting

### Problemas Comuns

1. **Container não inicia**:
```bash
docker compose logs web
docker compose exec web python manage.py check
```

2. **Erro de permissão**:
```bash
sudo chown -R 1000:1000 recordings media staticfiles
```

3. **Banco de dados não conecta**:
```bash
docker compose exec db psql -U dvr_user -d dvr_system
```

4. **Redis não conecta**:
```bash
docker compose exec redis redis-cli ping
```

5. **Gravações não funcionam**:
```bash
# Verificar FFmpeg
docker compose exec web ffmpeg -version

# Verificar permissões
ls -la recordings/
```

### Logs de Debug
```bash
# Ativar debug no .env
DEBUG=True

# Ver logs detalhados
docker compose logs -f --tail=100 web
```

## 📞 Suporte

Para suporte técnico:
- Verificar logs: `docker compose logs`
- Documentação: README.md
- Issues: GitHub Issues
- Comunidade: Discord/Slack

## 🔄 Atualizações

### Atualização Automática
```bash
#!/bin/bash
# update.sh

cd /path/to/dvr_system
git pull origin main
docker compose down
docker compose build --no-cache
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

### Agendar Atualizações
```bash
# Adicionar ao crontab
0 3 * * 0 /path/to/dvr_system/update.sh
```

---

**Sistema DVR - Deploy com Docker no Debian Bookworm** 🐳 