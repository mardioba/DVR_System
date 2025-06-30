from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import cv2
import numpy as np
import threading
import time
import json
from datetime import datetime, timedelta
import requests
from wsdiscovery import WSDiscovery
from onvif import ONVIFCamera

from .models import Camera, CameraSettings, CameraDiscovery
from .forms import CameraForm, CameraSettingsForm
from .utils import MotionDetector, StreamProcessor, ONVIFDiscovery


@login_required
def dashboard(request):
    """Dashboard principal com visualização das câmeras"""
    cameras = Camera.objects.filter(is_active=True).order_by('name')
    
    context = {
        'cameras': cameras,
        'total_cameras': cameras.count(),
        'online_cameras': cameras.filter(status='online').count(),
        'offline_cameras': cameras.filter(status='offline').count(),
    }
    
    return render(request, 'cameras/dashboard_new.html', context)


@login_required
def camera_list(request):
    """Lista todas as câmeras"""
    cameras = Camera.objects.all().order_by('name')
    
    context = {
        'cameras': cameras,
    }
    
    return render(request, 'cameras/camera_list.html', context)


@login_required
def camera_detail(request, camera_id):
    """Detalhes de uma câmera específica"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    try:
        settings = camera.settings
    except CameraSettings.DoesNotExist:
        settings = CameraSettings.objects.create(camera=camera)
    
    context = {
        'camera': camera,
        'settings': settings,
    }
    
    return render(request, 'cameras/camera_detail.html', context)


@login_required
def camera_create(request):
    """Criar nova câmera"""
    if request.method == 'POST':
        form = CameraForm(request.POST)
        if form.is_valid():
            camera = form.save()
            # Criar configurações padrão
            CameraSettings.objects.create(camera=camera)
            messages.success(request, f'Câmera "{camera.name}" criada com sucesso!')
            return redirect('cameras:camera_detail', camera_id=camera.id)
    else:
        form = CameraForm()
    
    context = {
        'form': form,
        'title': 'Adicionar Nova Câmera',
    }
    
    return render(request, 'cameras/camera_form.html', context)


@login_required
def camera_edit(request, camera_id):
    """Editar câmera existente"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    if request.method == 'POST':
        form = CameraForm(request.POST, instance=camera)
        if form.is_valid():
            camera = form.save()
            messages.success(request, f'Câmera "{camera.name}" atualizada com sucesso!')
            return redirect('cameras:camera_detail', camera_id=camera.id)
    else:
        form = CameraForm(instance=camera)
    
    context = {
        'form': form,
        'camera': camera,
        'title': f'Editar Câmera: {camera.name}',
    }
    
    return render(request, 'cameras/camera_form.html', context)


@login_required
def camera_delete(request, camera_id):
    """Excluir câmera"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    if request.method == 'POST':
        camera_name = camera.name
        camera.delete()
        messages.success(request, f'Câmera "{camera_name}" excluída com sucesso!')
        return redirect('cameras:camera_list')
    
    context = {
        'camera': camera,
    }
    
    return render(request, 'cameras/camera_confirm_delete.html', context)


@login_required
def camera_settings(request, camera_id):
    """Configurações de uma câmera"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    try:
        settings = camera.settings
    except CameraSettings.DoesNotExist:
        settings = CameraSettings.objects.create(camera=camera)
    
    if request.method == 'POST':
        form = CameraSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, f'Configurações da câmera "{camera.name}" atualizadas!')
            return redirect('cameras:camera_detail', camera_id=camera.id)
    else:
        form = CameraSettingsForm(instance=settings)
    
    context = {
        'form': form,
        'camera': camera,
        'settings': settings,
    }
    
    return render(request, 'cameras/camera_settings.html', context)


@login_required
def camera_live_view(request, camera_id):
    """Visualização ao vivo de uma câmera"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    context = {
        'camera': camera,
    }
    
    return render(request, 'cameras/camera_live_view.html', context)


def camera_stream(request, camera_id):
    """Stream de vídeo da câmera"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    def generate_frames():
        cap = cv2.VideoCapture(camera.get_stream_url())
        
        if not cap.isOpened():
            return
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Redimensionar frame para melhor performance
                frame = cv2.resize(frame, (640, 480))
                
                # Converter para JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    continue
                
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
        finally:
            cap.release()
    
    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')


def camera_snapshot(request, camera_id):
    """Captura um snapshot da câmera"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    try:
        cap = cv2.VideoCapture(camera.get_stream_url())
        
        if not cap.isOpened():
            # Retornar imagem placeholder se não conseguir conectar
            # Criar uma imagem placeholder simples
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            placeholder[:] = (128, 128, 128)  # Cinza
            
            # Adicionar texto
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(placeholder, 'Camera Offline', (200, 240), font, 1, (255, 255, 255), 2)
            cv2.putText(placeholder, 'RTSP Auth Required', (180, 280), font, 0.7, (200, 200, 200), 2)
            
            ret, buffer = cv2.imencode('.jpg', placeholder)
            if ret:
                response = HttpResponse(buffer.tobytes(), content_type='image/jpeg')
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                return response
        
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            # Redimensionar frame
            frame = cv2.resize(frame, (640, 480))
            
            # Converter para JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                response = HttpResponse(buffer.tobytes(), content_type='image/jpeg')
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                return response
        
        # Se não conseguir capturar, retornar placeholder
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        placeholder[:] = (128, 128, 128)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(placeholder, 'No Signal', (250, 240), font, 1, (255, 255, 255), 2)
        cv2.putText(placeholder, 'Camera Error', (220, 280), font, 0.7, (200, 200, 200), 2)
        
        ret, buffer = cv2.imencode('.jpg', placeholder)
        if ret:
            response = HttpResponse(buffer.tobytes(), content_type='image/jpeg')
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
            
    except Exception as e:
        # Em caso de erro, retornar placeholder
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        placeholder[:] = (128, 128, 128)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(placeholder, 'Error', (280, 240), font, 1, (255, 255, 255), 2)
        cv2.putText(placeholder, str(e)[:30], (200, 280), font, 0.5, (200, 200, 200), 1)
        
        ret, buffer = cv2.imencode('.jpg', placeholder)
        if ret:
            response = HttpResponse(buffer.tobytes(), content_type='image/jpeg')
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
    
    # Fallback
    return HttpResponse('Error', status=500)


@login_required
def camera_discovery(request):
    """Descoberta de câmeras na rede"""
    if request.method == 'POST':
        # Iniciar descoberta em background
        discovery_thread = threading.Thread(target=discover_cameras)
        discovery_thread.daemon = True
        discovery_thread.start()
        
        messages.info(request, 'Descoberta de câmeras iniciada. Aguarde alguns segundos...')
        return redirect('cameras:camera_discovery')
    
    discovered_cameras = CameraDiscovery.objects.filter(status='discovered').order_by('-discovered_at')
    
    context = {
        'discovered_cameras': discovered_cameras,
    }
    
    return render(request, 'cameras/camera_discovery.html', context)


@login_required
def add_discovered_camera(request, discovery_id):
    """Adicionar câmera descoberta ao sistema"""
    discovery = get_object_or_404(CameraDiscovery, id=discovery_id)
    
    if request.method == 'POST':
        # Criar nova câmera baseada na descoberta
        camera = Camera.objects.create(
            name=f"{discovery.manufacturer} {discovery.model}",
            ip_address=discovery.ip_address,
            port=discovery.port,
            stream_url=discovery.rtsp_url or f"rtsp://{discovery.ip_address}:554/stream1",
            camera_type='onvif' if discovery.onvif_url else 'rtsp',
        )
        
        # Criar configurações padrão
        CameraSettings.objects.create(camera=camera)
        
        # Marcar como adicionada
        discovery.status = 'added'
        discovery.added_at = timezone.now()
        discovery.save()
        
        messages.success(request, f'Câmera "{camera.name}" adicionada com sucesso!')
        return redirect('cameras:camera_detail', camera_id=camera.id)
    
    context = {
        'discovery': discovery,
    }
    
    return render(request, 'cameras/add_discovered_camera.html', context)


@login_required
def ignore_discovered_camera(request, discovery_id):
    """Ignorar câmera descoberta"""
    discovery = get_object_or_404(CameraDiscovery, id=discovery_id)
    discovery.status = 'ignored'
    discovery.save()
    
    messages.info(request, f'Câmera "{discovery.manufacturer} {discovery.model}" ignorada.')
    return redirect('cameras:camera_discovery')


# API Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_camera_list(request):
    """API para listar câmeras"""
    cameras = Camera.objects.all()
    data = []
    
    for camera in cameras:
        data.append({
            'id': str(camera.id),
            'name': camera.name,
            'status': camera.status,
            'ip_address': camera.ip_address,
            'stream_url': camera.stream_url,
            'is_active': camera.is_active,
            'last_seen': camera.last_seen.isoformat() if camera.last_seen else None,
        })
    
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_camera_status(request, camera_id):
    """API para atualizar status da câmera"""
    try:
        camera = Camera.objects.get(id=camera_id)
        status = request.data.get('status')
        
        if status in dict(Camera.CAMERA_STATUS):
            camera.update_status(status)
            return Response({'status': 'success'})
        else:
            return Response({'error': 'Status inválido'}, status=400)
            
    except Camera.DoesNotExist:
        return Response({'error': 'Câmera não encontrada'}, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def api_motion_detected(request, camera_id):
    """API para notificar detecção de movimento"""
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # Processar detecção de movimento
        if camera.motion_detection_enabled and camera.recording_enabled:
            # Iniciar gravação em background
            from recordings.tasks import start_motion_recording
            start_motion_recording.delay(str(camera.id))
        
        return JsonResponse({'status': 'success'})
        
    except Camera.DoesNotExist:
        return JsonResponse({'error': 'Câmera não encontrada'}, status=404)


def discover_cameras():
    """Função para descobrir câmeras na rede"""
    try:
        # Limpar descobertas antigas (mais de 1 hora)
        from django.utils import timezone
        from datetime import timedelta
        CameraDiscovery.objects.filter(
            discovered_at__lt=timezone.now() - timedelta(hours=1),
            status='discovered'
        ).update(status='ignored')
        
        # Método 1: Descoberta ONVIF via WSDiscovery
        try:
            from wsdiscovery import WSDiscovery
            from onvif import ONVIFCamera
            
            print("Iniciando descoberta ONVIF...")
            wsd = WSDiscovery()
            wsd.start()
            
            # Procurar por dispositivos ONVIF
            services = wsd.searchServices()
            print(f"Encontrados {len(services)} serviços ONVIF")
            
            for service in services:
                try:
                    service_url = service.getXAddrs()[0]
                    ip_address = service_url.split('://')[1].split(':')[0]
                    
                    print(f"Tentando conectar com {ip_address}...")
                    
                    # Tentar diferentes portas ONVIF
                    onvif_ports = [80, 8080, 8000]
                    connected = False
                    
                    for port in onvif_ports:
                        try:
                            cam = ONVIFCamera(ip_address, port, '', '')
                            device_info = cam.devicemgmt.GetDeviceInformation()
                            connected = True
                            break
                        except Exception as e:
                            print(f"  Tentativa porta {port} falhou: {e}")
                            continue
                    
                    if not connected:
                        # Se não conseguiu conectar via ONVIF, tentar identificar como câmera genérica
                        print(f"  Dispositivo {ip_address} encontrado mas não responde ao ONVIF")
                        
                        # Verificar se responde HTTP
                        try:
                            import requests
                            response = requests.get(f"http://{ip_address}:80", timeout=3)
                            
                            if response.status_code == 200:
                                # Criar registro como câmera genérica
                                CameraDiscovery.objects.update_or_create(
                                    ip_address=ip_address,
                                    defaults={
                                        'manufacturer': 'Desconhecido',
                                        'model': 'Câmera IP',
                                        'serial_number': '',
                                        'firmware_version': '',
                                        'onvif_url': f"http://{ip_address}:80",
                                        'rtsp_url': f"rtsp://{ip_address}:554/stream1",
                                        'status': 'discovered',
                                        'discovered_at': timezone.now(),
                                    }
                                )
                                print(f"  Câmera genérica descoberta: {ip_address}")
                        except:
                            pass
                        
                        continue
                    
                    # Tentar obter URL do stream RTSP
                    rtsp_url = None
                    try:
                        media_service = cam.create_media_service()
                        profiles = media_service.GetProfiles()
                        
                        if profiles:
                            stream_uri = media_service.GetStreamUri({
                                'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}},
                                'ProfileToken': profiles[0].token
                            })
                            rtsp_url = stream_uri.Uri
                    except Exception as e:
                        print(f"  Erro ao obter stream RTSP para {ip_address}: {e}")
                        rtsp_url = f"rtsp://{ip_address}:554/stream1"
                    
                    # Criar ou atualizar registro de descoberta
                    CameraDiscovery.objects.update_or_create(
                        ip_address=ip_address,
                        defaults={
                            'manufacturer': device_info.Manufacturer or 'Desconhecido',
                            'model': device_info.Model or 'Desconhecido',
                            'serial_number': device_info.SerialNumber or '',
                            'firmware_version': device_info.FirmwareVersion or '',
                            'onvif_url': service_url,
                            'rtsp_url': rtsp_url,
                            'status': 'discovered',
                            'discovered_at': timezone.now(),
                        }
                    )
                    
                    print(f"  Câmera ONVIF descoberta: {device_info.Manufacturer} {device_info.Model} ({ip_address})")
                    
                except Exception as e:
                    print(f"  Erro ao conectar com câmera ONVIF {ip_address}: {e}")
                    continue
            
            wsd.stop()
            
        except Exception as e:
            print(f"Erro na descoberta ONVIF: {e}")
        
        # Método 2: Descoberta por varredura de IP comum
        try:
            print("Iniciando varredura de IP comum...")
            import socket
            import threading
            import time
            
            def check_camera_port(ip, port):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    return result == 0
                except:
                    return False
            
            # Lista de portas comuns para câmeras
            camera_ports = [80, 443, 554, 8080, 8000, 9000]
            
            # Varredura de IPs na rede local (192.168.1.x)
            base_ip = "192.168.1"
            
            for i in range(1, 255):
                ip = f"{base_ip}.{i}"
                
                # Verificar se já existe uma descoberta para este IP
                if CameraDiscovery.objects.filter(ip_address=ip).exists():
                    continue
                
                # Verificar portas comuns
                for port in camera_ports:
                    if check_camera_port(ip, port):
                        # Tentar identificar como câmera
                        try:
                            # Tentar conectar via HTTP
                            import requests
                            response = requests.get(f"http://{ip}:{port}", timeout=3)
                            
                            # Verificar se é uma câmera baseado no conteúdo da resposta
                            if any(keyword in response.text.lower() for keyword in ['camera', 'ipcam', 'webcam', 'surveillance']):
                                CameraDiscovery.objects.create(
                                    ip_address=ip,
                                    port=port,
                                    manufacturer='Desconhecido',
                                    model='Câmera IP',
                                    onvif_url=f"http://{ip}:{port}",
                                    rtsp_url=f"rtsp://{ip}:554/stream1",
                                    status='discovered',
                                )
                                print(f"  Câmera IP descoberta: {ip}:{port}")
                                break
                                
                        except Exception as e:
                            continue
                            
        except Exception as e:
            print(f"Erro na varredura de IP: {e}")
        
        # Método 3: Descoberta via broadcast UDP
        try:
            print("Iniciando descoberta via broadcast...")
            import socket
            
            # Socket para broadcast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(5)
            
            # Enviar broadcast para descoberta
            broadcast_message = b"ONVIF_DISCOVERY"
            sock.sendto(broadcast_message, ('<broadcast>', 3702))
            
            # Aguardar respostas
            time.sleep(3)
            
            try:
                while True:
                    data, addr = sock.recvfrom(1024)
                    ip = addr[0]
                    
                    # Verificar se já existe descoberta para este IP
                    if not CameraDiscovery.objects.filter(ip_address=ip).exists():
                        CameraDiscovery.objects.create(
                            ip_address=ip,
                            manufacturer='Descoberta via Broadcast',
                            model='Câmera IP',
                            onvif_url=f"http://{ip}:80",
                            rtsp_url=f"rtsp://{ip}:554/stream1",
                            status='discovered',
                        )
                        print(f"  Câmera descoberta via broadcast: {ip}")
                        
            except socket.timeout:
                pass
                
            sock.close()
            
        except Exception as e:
            print(f"Erro na descoberta via broadcast: {e}")
        
        print("Descoberta de câmeras concluída!")
        
    except Exception as e:
        print(f"Erro geral na descoberta de câmeras: {e}")


@login_required
def camera_manual_recording(request, camera_id):
    """Iniciar gravação manual"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    if request.method == 'POST':
        duration = int(request.POST.get('duration', 30))
        
        # Iniciar gravação manual em background
        from recordings.tasks import start_manual_recording
        start_manual_recording.delay(str(camera.id), duration)
        
        messages.success(request, f'Gravação manual iniciada para "{camera.name}" por {duration} segundos.')
        return redirect('cameras:camera_detail', camera_id=camera.id)
    
    context = {
        'camera': camera,
    }
    
    return render(request, 'cameras/camera_manual_recording.html', context) 