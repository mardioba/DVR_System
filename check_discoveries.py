#!/usr/bin/env python3
"""
Script simples para verificar câmeras descobertas
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dvr_system.settings')
django.setup()

from cameras.models import CameraDiscovery

def check_discoveries():
    """Verifica câmeras descobertas"""
    print("=== Verificação de Câmeras Descobertas ===")
    
    # Todas as descobertas
    all_discoveries = CameraDiscovery.objects.all()
    print(f"Total de registros: {all_discoveries.count()}")
    
    # Por status
    discovered = CameraDiscovery.objects.filter(status='discovered')
    added = CameraDiscovery.objects.filter(status='added')
    ignored = CameraDiscovery.objects.filter(status='ignored')
    
    print(f"Status 'discovered': {discovered.count()}")
    print(f"Status 'added': {added.count()}")
    print(f"Status 'ignored': {ignored.count()}")
    
    print("\nCâmeras descobertas:")
    for camera in discovered:
        print(f"  - {camera.manufacturer} {camera.model} ({camera.ip_address})")
        print(f"    Porta: {camera.port}")
        print(f"    ONVIF: {camera.onvif_url}")
        print(f"    RTSP: {camera.rtsp_url}")
        print(f"    Descoberto: {camera.discovered_at}")
        print()

if __name__ == "__main__":
    check_discoveries() 