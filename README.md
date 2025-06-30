# Sistema DVR - Central de Monitoramento de Câmeras IP

Um sistema completo de monitoramento de câmeras IP inspirado no Frigate, desenvolvido em Django com interface moderna e funcionalidades avançadas.

## 🚀 Funcionalidades

### 📹 Monitoramento de Câmeras IP
- **Cadastro de câmeras** com nome, IP/URL, usuário e senha
- **Suporte a múltiplos protocolos**: RTSP, HTTP, ONVIF, RTMP
- **Visualização ao vivo** com miniaturas das câmeras
- **Status em tempo real** (online/offline/erro)
- **Descoberta automática** de câmeras na rede via ONVIF

### 🧠 Backend Django
- **Modelos robustos** para câmeras, gravações e eventos
- **Autenticação de usuários** com login/logout
- **Dashboard interativo** com estatísticas
- **API REST** para integração externa
- **Tarefas em background** com Celery

### 💾 Sistema de Gravação
- **Detecção de movimento** inteligente
- **Gravação automática** por 30 segundos ao detectar movimento
- **Gravação manual** sob demanda
- **Controle de retenção** configurável (dias)
- **Formato H.264** para compatibilidade com navegadores
- **Compressão automática** para economia de espaço

### 🌐 Interface Web
- **Design responsivo** com Bootstrap 5
- **Menu lateral** para navegação rápida
- **Tema moderno** com gradientes e animações
- **Visualização de streams** em tempo real
- **Reprodução de gravações** integrada

## 🛠️ Tecnologias Utilizadas

- **Backend**: Django 4.2.7, Python 3.8+
- **Frontend**: Bootstrap 5, JavaScript
- **Banco de Dados**: SQLite (padrão), PostgreSQL (produção)
- **Processamento de Vídeo**: OpenCV, FFmpeg
- **Tarefas em Background**: Celery, Redis
- **Descoberta de Câmeras**: WSDiscovery, ONVIF
- **Autenticação**: Django Auth System

## 📋 Pré-requisitos

- Python 3.8 ou superior
- FFmpeg instalado no sistema
- Redis (para tarefas em background)
- Acesso à rede local para descoberta de câmeras

## 🔧 Instalação

### 1. Clone o repositório
```bash
git clone <url-do-repositorio>
cd DVR_System
```

### 2. Crie um ambiente virtual
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente
Crie um arquivo `.env` na raiz do projeto:
```env
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
RECORDINGS_PATH=/path/to/recordings
MAX_RECORDING_DAYS=30
```

### 5. Execute as migrações
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Crie um superusuário
```bash
python manage.py createsuperuser
```

### 7. Inicie o servidor
```bash
python manage.py runserver
```

### 8. Inicie o Celery (em outro terminal)
```bash
celery -A dvr_system worker -l info
```

### 9. Inicie o Celery Beat (para tarefas agendadas)
```bash
celery -A dvr_system beat -l info
```

## 🎯 Como Usar

### 1. Acesse o sistema
- Abra o navegador e acesse `http://localhost:8000`
- Faça login com as credenciais criadas

### 2. Adicione câmeras
- Vá em "Câmeras" → "Adicionar Câmera"
- Preencha as informações da câmera:
  - **Nome**: Nome descritivo da câmera
  - **IP**: Endereço IP da câmera
  - **URL do Stream**: URL completa do stream (ex: `rtsp://192.168.1.100:554/stream1`)
  - **Usuário/Senha**: Se necessário para autenticação
  - **Tipo**: Protocolo da câmera (RTSP, HTTP, etc.)

### 3. Descoberta automática
- Vá em "Descoberta" para encontrar câmeras ONVIF na rede
- Clique em "Adicionar" nas câmeras descobertas

### 4. Configure gravações
- Acesse "Configurações" para definir:
  - Dias de retenção das gravações
  - Limite de armazenamento
  - Compressão automática

### 5. Visualize ao vivo
- No dashboard, veja todas as câmeras em tempo real
- Clique em uma câmera para visualização em tela cheia

## 📁 Estrutura do Projeto

```
DVR_System/
├── dvr_system/          # Configurações principais
├── cameras/             # App de câmeras
│   ├── models.py       # Modelos de câmeras
│   ├── views.py        # Views e lógica
│   ├── forms.py        # Formulários
│   └── utils.py        # Utilitários de vídeo
├── recordings/          # App de gravações
│   ├── models.py       # Modelos de gravações
│   ├── views.py        # Views de gravações
│   └── tasks.py        # Tarefas Celery
├── users/              # App de usuários
├── templates/          # Templates HTML
├── static/             # Arquivos estáticos
├── media/              # Arquivos de mídia
└── recordings/         # Diretório de gravações
```

## 🔧 Configuração Avançada

### Configuração do FFmpeg
Certifique-se de que o FFmpeg está instalado e acessível:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg

# macOS
brew install ffmpeg
```

### Configuração do Redis
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis
```

### Configuração de Produção
Para produção, recomenda-se:
- Usar PostgreSQL como banco de dados
- Configurar HTTPS
- Usar um servidor WSGI como Gunicorn
- Configurar Nginx como proxy reverso
- Usar Redis Cluster para alta disponibilidade

## 🐛 Solução de Problemas

### Câmera não conecta
1. Verifique se o IP e porta estão corretos
2. Teste a URL do stream em um player VLC
3. Verifique se as credenciais estão corretas
4. Confirme se a câmera suporta o protocolo escolhido

### Gravações não funcionam
1. Verifique se o FFmpeg está instalado
2. Confirme se o diretório de gravações tem permissões de escrita
3. Verifique os logs do Celery para erros
4. Confirme se a detecção de movimento está habilitada

### Performance lenta
1. Reduza a resolução das câmeras
2. Diminua a taxa de frames
3. Use compressão mais agressiva
4. Considere usar hardware de aceleração

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## 🤝 Contribuição

Contribuições são bem-vindas! Por favor:
1. Faça um fork do projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📞 Suporte

Para suporte e dúvidas:
- Abra uma issue no GitHub
- Consulte a documentação
- Verifique os logs do sistema

## 🔄 Atualizações

Para atualizar o sistema:
```bash
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic
```

---

**Desenvolvido com ❤️ para monitoramento de câmeras IP** 