#!/bin/bash

# Script para parar todos os serviços do Sistema DVR
# Uso: ./stop_services.sh

echo "🛑 Parando Sistema DVR..."
echo "========================"

# Parar Django
echo "🔄 Parando Django Server..."
pkill -f "manage.py.*runserver" || echo "  Django não estava rodando"

# Parar Celery Beat
echo "🔄 Parando Celery Beat..."
pkill -f "celery.*beat" || echo "  Celery Beat não estava rodando"

# Parar Celery Worker
echo "🔄 Parando Celery Worker..."
pkill -f "celery.*worker" || echo "  Celery Worker não estava rodando"

# Parar Redis (opcional - comentado para não afetar outros serviços)
# echo "🔄 Parando Redis..."
# pkill -x "redis-server" || echo "  Redis não estava rodando"

echo ""
echo "✅ Todos os serviços parados!"
echo ""
echo "💡 Para iniciar novamente, execute: ./start_services.sh" 