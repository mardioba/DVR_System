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
    print(f"🔄 {description}...")
    try:
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} concluído!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro em {description}: {e}")
        print(f"Comando: {command}")
        print(f"Erro: {e.stderr}")
        return False


def check_python_version():
    print("🐍 Verificando versão do Python...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ é necessário. Versão atual: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK!")
    return True


def install_ffmpeg_if_needed():
    print("🎬 Verificando FFmpeg...")
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg já está instalado!")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("❌ FFmpeg não encontrado.")
        return run_command("sudo apt install -y ffmpeg", "Instalando FFmpeg")


def install_redis():
    return run_command("sudo apt install -y redis-server", "Instalando Redis")


def install_celery():
    _, venv_pip = get_venv_python_and_pip()
    return run_command(f'"{venv_pip}" install celery', "Instalando Celery via pip")


def install_mariadb_and_create_db():
    print("🛠️ Instalando MariaDB e configurando banco de dados...")
    if not run_command("sudo apt update && sudo apt install -y mariadb-server", "Instalando MariaDB"):
        return False

    db_commands = """
CREATE DATABASE IF NOT EXISTS monitoramento CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER IF NOT EXISTS 'monit'@'localhost' IDENTIFIED BY 'monit123';
GRANT ALL PRIVILEGES ON monitoramento.* TO 'monit'@'localhost';
FLUSH PRIVILEGES;
"""
    with open("db_setup.sql", "w") as f:
        f.write(db_commands)

    if not run_command("sudo mariadb < db_setup.sql", "Configurando banco de dados MariaDB"):
        return False

    os.remove("db_setup.sql")
    return True


def install_system_dependencies():
    print("🔧 Instalando dependências do sistema para mysqlclient...")
    packages = [
        "pkg-config",
        "libmariadb-dev",
        "default-libmysqlclient-dev",
        "build-essential",
        "python3-dev"
    ]
    return run_command(f"sudo apt install -y {' '.join(packages)}", "Instalando dependências do sistema")


def create_env_file():
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


def get_venv_python_and_pip():
    venv_path = Path('venv')
    if platform.system().lower() == "windows":
        venv_python = venv_path / 'Scripts' / 'python.exe'
        venv_pip = venv_path / 'Scripts' / 'pip.exe'
    else:
        venv_python = venv_path / 'bin' / 'python'
        venv_pip = venv_path / 'bin' / 'pip'
    return str(venv_python), str(venv_pip)


def setup_virtual_environment():
    venv_path = Path('venv')
    python_path = sys.executable
    if not venv_path.exists():
        print("🔧 Criando ambiente virtual...")
        if not run_command(f'"{python_path}" -m venv venv', 'Criando ambiente virtual'):
            return False
    venv_python, _ = get_venv_python_and_pip()
    if not Path(venv_python).exists():
        print("❌ Python do venv não encontrado!")
        return False
    print(f"✅ Ambiente virtual configurado! Usando Python do venv: {venv_python}")
    return True


def install_dependencies():
    _, venv_pip = get_venv_python_and_pip()
    return run_command(f'"{venv_pip}" install -r requirements.txt', 'Instalando dependências')


def run_django_commands():
    venv_python, _ = get_venv_python_and_pip()
    commands = [
        (f'"{venv_python}" manage.py makemigrations', 'Criando migrações'),
        (f'"{venv_python}" manage.py migrate', 'Executando migrações'),
        (f'"{venv_python}" manage.py collectstatic --noinput', 'Coletando arquivos estáticos'),
    ]
    for command, description in commands:
        if not run_command(command, description):
            return False
    return True


def create_superuser():
    resp = input("\n🤔 Deseja criar um superusuário agora? (s/n): ").lower()
    if resp in ['s', 'sim', 'y', 'yes']:
        venv_python, _ = get_venv_python_and_pip()
        run_command(f'"{venv_python}" manage.py createsuperuser', 'Criando superusuário')


def create_recordings_files():
    recordings_dir = Path('recordings')
    recordings_dir.mkdir(parents=True, exist_ok=True)
    (recordings_dir / '__init__.py').touch(exist_ok=True)
    (recordings_dir / 'models.py').touch(exist_ok=True)


def fix_permissions():
    try:
        print("🔒 Ajustando permissões da pasta do projeto...")
        os.system(f'chown -R $USER:$USER {os.getcwd()}')
        os.system(f'chmod -R 755 {os.getcwd()}')
        print("✅ Permissões ajustadas!")
    except Exception as e:
        print(f"⚠️ Erro ao ajustar permissões: {e}")


def main():
    print("🚀 Sistema DVR - Setup")
    print("=" * 50)

    if not check_python_version():
        sys.exit(1)

    if not install_mariadb_and_create_db():
        sys.exit(1)

    if not install_system_dependencies():
        sys.exit(1)

    if not install_ffmpeg_if_needed():
        sys.exit(1)

    if not install_redis():
        sys.exit(1)

    create_recordings_files()
    fix_permissions()
    create_env_file()

    if not setup_virtual_environment():
        sys.exit(1)

    if not install_dependencies():
        sys.exit(1)

    if not install_celery():
        sys.exit(1)

    if not run_django_commands():
        sys.exit(1)

    create_superuser()

    print("\n🎉 Setup concluído com sucesso!")
    print("\n📋 Próximos passos:")
    print("1. Inicie o Redis: `redis-server`")
    print("2. Inicie o Celery: `celery -A dvr_system worker -l info`")
    print("3. Inicie o servidor Django: `python manage.py runserver`")
    print("4. Acesse: http://localhost:8000")


if __name__ == "__main__":
    main()
