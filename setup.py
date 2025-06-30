#!/usr/bin/env python3
"""
Script de setup para o Sistema DVR
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def run_command(command, description):
    """Executa um comando e mostra o progresso"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} concluído!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro em {description}: {e}")
        print(f"Comando: {command}")
        print(f"Erro: {e.stderr}")
        return False


def check_python_version():
    """Verifica se a versão do Python é compatível"""
    print("🐍 Verificando versão do Python...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ é necessário. Versão atual: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK!")
    return True


def check_ffmpeg():
    """Verifica se o FFmpeg está instalado"""
    print("🎬 Verificando FFmpeg...")
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg encontrado!")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ FFmpeg não encontrado!")
    print("📋 Instale o FFmpeg:")
    
    system = platform.system().lower()
    if system == "linux":
        print("  Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg")
        print("  CentOS/RHEL: sudo yum install ffmpeg")
    elif system == "darwin":
        print("  macOS: brew install ffmpeg")
    elif system == "windows":
        print("  Windows: Baixe de https://ffmpeg.org/download.html")
    
    return False


def create_env_file():
    """Cria arquivo .env se não existir"""
    env_file = Path('.env')
    if not env_file.exists():
        print("📝 Criando arquivo .env...")
        env_content = """# Configurações do Sistema DVR
SECRET_KEY=django-insecure-change-this-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Celery/REDIS
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# DVR Settings
RECORDINGS_PATH=./recordings
MAX_RECORDING_DAYS=30
MOTION_DETECTION_SENSITIVITY=0.3
RECORDING_DURATION=30
MOTION_TIMEOUT=4
MOTION_START_DELAY=10
FRAME_RATE=15
"""
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ Arquivo .env criado!")
    else:
        print("✅ Arquivo .env já existe!")


def setup_virtual_environment():
    """Configura ambiente virtual"""
    venv_path = Path('venv')
    if not venv_path.exists():
        print("🔧 Criando ambiente virtual...")
        if not run_command('python -m venv venv', 'Criando ambiente virtual'):
            return False
    
    # Ativar ambiente virtual
    if platform.system().lower() == "windows":
        activate_script = venv_path / 'Scripts' / 'activate.bat'
        python_path = venv_path / 'Scripts' / 'python.exe'
        pip_path = venv_path / 'Scripts' / 'pip.exe'
    else:
        activate_script = venv_path / 'bin' / 'activate'
        python_path = venv_path / 'bin' / 'python'
        pip_path = venv_path / 'bin' / 'pip'
    
    if not python_path.exists():
        print("❌ Ambiente virtual não foi criado corretamente!")
        return False
    
    print("✅ Ambiente virtual configurado!")
    return True


def install_dependencies():
    """Instala dependências Python"""
    venv_path = Path('venv')
    if platform.system().lower() == "windows":
        pip_path = venv_path / 'Scripts' / 'pip.exe'
    else:
        pip_path = venv_path / 'bin' / 'pip'
    
    if not run_command(f'"{pip_path}" install -r requirements.txt', 'Instalando dependências'):
        return False
    
    return True


def run_django_commands():
    """Executa comandos Django necessários"""
    venv_path = Path('venv')
    if platform.system().lower() == "windows":
        python_path = venv_path / 'Scripts' / 'python.exe'
    else:
        python_path = venv_path / 'bin' / 'python'
    
    commands = [
        (f'"{python_path}" manage.py makemigrations', 'Criando migrações'),
        (f'"{python_path}" manage.py migrate', 'Executando migrações'),
        (f'"{python_path}" manage.py collectstatic --noinput', 'Coletando arquivos estáticos'),
    ]
    
    for command, description in commands:
        if not run_command(command, description):
            return False
    
    return True


def create_superuser():
    """Cria superusuário se solicitado"""
    response = input("\n🤔 Deseja criar um superusuário agora? (s/n): ").lower()
    if response in ['s', 'sim', 'y', 'yes']:
        venv_path = Path('venv')
        if platform.system().lower() == "windows":
            python_path = venv_path / 'Scripts' / 'python.exe'
        else:
            python_path = venv_path / 'bin' / 'python'
        
        run_command(f'"{python_path}" manage.py createsuperuser', 'Criando superusuário')
    else:
        print("ℹ️  Você pode criar um superusuário depois com: python manage.py createsuperuser")


def create_recordings_files():
    """Garante que recordings/__init__.py e recordings/models.py existem."""
    recordings_dir = Path('recordings')
    init_file = recordings_dir / '__init__.py'
    models_file = recordings_dir / 'models.py'
    if not recordings_dir.exists():
        print("📁 Criando diretório 'recordings'...")
        recordings_dir.mkdir(parents=True, exist_ok=True)
    if not init_file.exists():
        print("📝 Criando recordings/__init__.py...")
        init_file.touch()
        print("✅ recordings/__init__.py criado!")
    else:
        print("✅ recordings/__init__.py já existe!")
    if not models_file.exists():
        print("📝 Criando recordings/models.py...")
        models_file.touch()
        print("✅ recordings/models.py criado!")
    else:
        print("✅ recordings/models.py já existe!")


def fix_permissions():
    """Garante permissões corretas na pasta do projeto."""
    try:
        print("🔒 Ajustando permissões da pasta do projeto...")
        os.system(f'chown -R $USER:$USER {os.getcwd()}')
        os.system(f'chmod -R 755 {os.getcwd()}')
        print("✅ Permissões ajustadas!")
    except Exception as e:
        print(f"⚠️ Erro ao ajustar permissões: {e}")


def main():
    """Função principal do setup"""
    print("🚀 Sistema DVR - Setup")
    print("=" * 50)
    
    # Verificações iniciais
    if not check_python_version():
        sys.exit(1)
    
    if not check_ffmpeg():
        print("⚠️  Continue sem FFmpeg? (s/n): ", end="")
        if input().lower() not in ['s', 'sim', 'y', 'yes']:
            sys.exit(1)
    
    # Garante que recordings/__init__.py e models.py existem
    create_recordings_files()
    # Ajusta permissões do projeto
    fix_permissions()
    # Configuração do projeto
    create_env_file()
    
    if not setup_virtual_environment():
        sys.exit(1)
    
    if not install_dependencies():
        sys.exit(1)
    
    if not run_django_commands():
        sys.exit(1)
    
    create_superuser()
    
    print("\n🎉 Setup concluído com sucesso!")
    print("\n📋 Próximos passos:")
    print("1. Inicie o Redis: redis-server")
    print("2. Inicie o Celery: celery -A dvr_system worker -l info")
    print("3. Inicie o servidor: python manage.py runserver")
    print("4. Acesse: http://localhost:8000")
    print("\n📖 Consulte o README.md para mais informações!")


if __name__ == "__main__":
    main() 