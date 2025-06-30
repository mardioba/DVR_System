from django.core.management.base import BaseCommand
from cameras.models import Camera
from django.utils import timezone
import requests
import socket
import cv2
import threading
import time


class Command(BaseCommand):
    help = 'Verifica o status de todas as câmeras no sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--camera-id',
            type=str,
            help='ID específico da câmera para verificar',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=5,
            help='Timeout em segundos para conexões (padrão: 5)',
        )

    def handle(self, *args, **options):
        camera_id = options.get('camera_id')
        timeout = options.get('timeout')

        if camera_id:
            try:
                camera = Camera.objects.get(id=camera_id)
                self.check_camera_status(camera, timeout)
            except Camera.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Câmera com ID {camera_id} não encontrada')
                )
        else:
            cameras = Camera.objects.filter(is_active=True)
            self.stdout.write(f'Verificando status de {cameras.count()} câmeras...')
            
            for camera in cameras:
                self.check_camera_status(camera, timeout)

    def check_camera_status(self, camera, timeout):
        """Verifica o status de uma câmera específica"""
        self.stdout.write(f'\nVerificando {camera.name} ({camera.ip_address})...')
        
        # Método 1: Verificar conectividade de rede
        network_status = self.check_network_connectivity(camera.ip_address, camera.port, timeout)
        
        # Método 2: Verificar HTTP (se aplicável)
        http_status = self.check_http_connectivity(camera.ip_address, camera.port, timeout)
        
        # Método 3: Verificar stream RTSP
        rtsp_status = self.check_rtsp_stream(camera.stream_url, timeout)
        
        # Determinar status final
        if rtsp_status:
            status = 'online'
            self.stdout.write(self.style.SUCCESS('  ✅ Status: Online (RTSP funcionando)'))
        elif http_status:
            status = 'online'
            self.stdout.write(self.style.SUCCESS('  ✅ Status: Online (HTTP funcionando)'))
        elif network_status:
            status = 'online'
            self.stdout.write(self.style.SUCCESS('  ✅ Status: Online (Rede acessível)'))
        else:
            status = 'offline'
            self.stdout.write(self.style.ERROR('  ❌ Status: Offline'))
        
        # Atualizar status no banco
        if camera.status != status:
            camera.status = status
            if status == 'online':
                camera.last_seen = timezone.now()
            camera.save()
            self.stdout.write(f'  📝 Status atualizado no banco: {status}')
        else:
            self.stdout.write(f'  ℹ️  Status já estava: {status}')

    def check_network_connectivity(self, ip, port, timeout):
        """Verifica se a câmera responde na rede"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception as e:
            return False

    def check_http_connectivity(self, ip, port, timeout):
        """Verifica se a câmera responde HTTP"""
        try:
            url = f"http://{ip}:{port}"
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            return False

    def check_rtsp_stream(self, stream_url, timeout):
        """Verifica se o stream RTSP está funcionando"""
        try:
            # Tentar abrir o stream com OpenCV
            cap = cv2.VideoCapture(stream_url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)
            
            if cap.isOpened():
                # Tentar ler um frame
                ret, frame = cap.read()
                cap.release()
                return ret
            else:
                cap.release()
                return False
        except Exception as e:
            return False 