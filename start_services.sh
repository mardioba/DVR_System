#!/bin/bash

# Script para iniciar todos os serviços do Sistema DVR
# Uso: ./start_services.sh

set -e

echo "🚀 Iniciando Sistema DVR..."
echo "=========================="

# Verificar se estamos no diretório correto
if [ ! -f "manage.py" ]; then
    echo "❌ Erro: Execute este script no diretório raiz do projeto"
    exit 1
fi

# Verificar se o ambiente virtual existe
if [ ! -d "venv" ]; then
    echo "❌ Erro: Ambiente virtual não encontrado. Execute setup.py primeiro"
    exit 1
fi

# Ativar ambiente virtual
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

# Verificar se o Redis está rodando
echo "🔍 Verificando Redis..."
if ! pgrep -x "redis-server" > /dev/null; then
    echo "⚠️  Redis não está rodando. Iniciando..."
    redis-server --daemonize yes
    sleep 2
else
    echo "✅ Redis já está rodando"
fi

# Verificar se o Celery está rodando
echo "🔍 Verificando Celery..."
if ! pgrep -f "celery.*worker" > /dev/null; then
    echo "🔄 Iniciando Celery Worker..."
    celery -A dvr_system worker -l info --detach
    sleep 2
else
    echo "✅ Celery Worker já está rodando"
fi

# Verificar se o Celery Beat está rodando
echo "🔍 Verificando Celery Beat..."
if ! pgrep -f "celery.*beat" > /dev/null; then
    echo "🔄 Iniciando Celery Beat..."
    celery -A dvr_system beat -l info --detach
    sleep 2
else
    echo "✅ Celery Beat já está rodando"
fi

# Verificar se o Django está rodando
echo "🔍 Verificando Django..."
if ! pgrep -f "manage.py.*runserver" > /dev/null; then
    echo "🔄 Iniciando Django Server..."
    python manage.py runserver 0.0.0.0:8000 &
    sleep 3
else
    echo "✅ Django Server já está rodando"
fi

echo ""
echo "🎉 Todos os serviços iniciados com sucesso!"
echo ""
echo "📋 Serviços ativos:"
echo "  • Redis: redis-server"
echo "  • Celery Worker: celery -A dvr_system worker"
echo "  • Celery Beat: celery -A dvr_system beat"
echo "  • Django: python manage.py runserver"
echo ""
echo "🌐 Acesse o sistema em: http://localhost:8000"
echo ""
echo "📖 Para parar todos os serviços, execute: ./stop_services.sh"
echo "📖 Para ver logs: tail -f celery.log" 