#!/usr/bin/env python3
"""
Script para limpar descobertas antigas e testar novamente
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dvr_system.settings')
django.setup()

from cameras.models import CameraDiscovery
from django.utils import timezone

def clear_discoveries():
    """Limpa todas as descobertas antigas"""
    print("=== Limpando Descobertas ===")
    
    # Contar descobertas existentes
    total_discoveries = CameraDiscovery.objects.count()
    discovered_count = CameraDiscovery.objects.filter(status='discovered').count()
    added_count = CameraDiscovery.objects.filter(status='added').count()
    ignored_count = CameraDiscovery.objects.filter(status='ignored').count()
    
    print(f"Total de descobertas: {total_discoveries}")
    print(f"  - Descobertas: {discovered_count}")
    print(f"  - Adicionadas: {added_count}")
    print(f"  - Ignoradas: {ignored_count}")
    
    # Limpar todas as descobertas
    CameraDiscovery.objects.all().delete()
    print("✅ Todas as descobertas foram removidas!")
    
    # Verificar se foi limpo
    remaining = CameraDiscovery.objects.count()
    print(f"Descobertas restantes: {remaining}")

if __name__ == "__main__":
    clear_discoveries() 