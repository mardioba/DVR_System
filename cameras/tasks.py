from celery import shared_task
from cameras.models import Camera
from recordings.models import Recording, MotionEvent
from django.utils import timezone
import requests
import socket
import cv2
import time
import os
import numpy as np
from datetime import timedelta
import threading
import queue


@shared_task
def check_camera_status_task(camera_id=None):
    """Tarefa para verificar status das câmeras"""
    if camera_id:
        try:
            camera = Camera.objects.get(id=camera_id)
            check_single_camera_status(camera)
        except Camera.DoesNotExist:
            pass
    else:
        cameras = Camera.objects.filter(is_active=True)
        for camera in cameras:
            check_single_camera_status(camera)


def check_single_camera_status(camera):
    """Verifica o status de uma câmera específica"""
    try:
        # Verificar conectividade de rede
        network_status = check_network_connectivity(camera.ip_address, camera.port)
        
        # Verificar HTTP
        http_status = check_http_connectivity(camera.ip_address, camera.port)
        
        # Verificar RTSP (opcional, pode falhar por autenticação)
        rtsp_status = check_rtsp_stream(camera.stream_url)
        
        # Determinar status final
        if rtsp_status or http_status or network_status:
            new_status = 'online'
        else:
            new_status = 'offline'
        
        # Atualizar status se mudou
        if camera.status != new_status:
            camera.status = new_status
            if new_status == 'online':
                camera.last_seen = timezone.now()
            camera.save()
            
    except Exception as e:
        # Em caso de erro, marcar como offline
        if camera.status != 'offline':
            camera.status = 'offline'
            camera.save()


def check_network_connectivity(ip, port, timeout=3):
    """Verifica conectividade de rede"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False


def check_http_connectivity(ip, port, timeout=3):
    """Verifica conectividade HTTP"""
    try:
        url = f"http://{ip}:{port}"
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except:
        return False


def check_rtsp_stream(stream_url, timeout=3):
    """Verifica stream RTSP"""
    try:
        cap = cv2.VideoCapture(stream_url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)
        
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            return ret
        else:
            cap.release()
            return False
    except:
        return False


@shared_task
def update_all_cameras_status():
    """Atualiza status de todas as câmeras"""
    cameras = Camera.objects.filter(is_active=True)
    for camera in cameras:
        check_single_camera_status(camera)


@shared_task
def cleanup_old_discoveries():
    """Remove descobertas antigas"""
    from cameras.models import CameraDiscovery
    from datetime import timedelta
    
    # Remover descobertas com mais de 24 horas
    old_discoveries = CameraDiscovery.objects.filter(
        discovered_at__lt=timezone.now() - timedelta(hours=24),
        status='discovered'
    )
    count = old_discoveries.count()
    old_discoveries.update(status='ignored')
    
    return f"Removidas {count} descobertas antigas"


# Variáveis globais para controle de gravação
recording_threads = {}
motion_detection_active = {}


@shared_task
def start_motion_detection(camera_id):
    """Inicia detecção de movimento para uma câmera"""
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # Verificar se já está ativo
        if camera_id in motion_detection_active and motion_detection_active[camera_id]:
            return f"Detecção já ativa para {camera.name}"
        
        # Iniciar thread de detecção
        motion_detection_active[camera_id] = True
        thread = threading.Thread(
            target=motion_detection_worker,
            args=(camera_id,),
            daemon=True
        )
        thread.start()
        
        return f"Detecção iniciada para {camera.name}"
        
    except Camera.DoesNotExist:
        return f"Câmera {camera_id} não encontrada"


@shared_task
def stop_motion_detection(camera_id):
    """Para detecção de movimento para uma câmera"""
    try:
        camera = Camera.objects.get(id=camera_id)
        motion_detection_active[camera_id] = False
        
        # Parar gravação se estiver ativa
        if camera_id in recording_threads:
            recording_threads[camera_id]['stop'] = True
        
        return f"Detecção parada para {camera.name}"
        
    except Camera.DoesNotExist:
        return f"Câmera {camera_id} não encontrada"


def motion_detection_worker(camera_id):
    """Worker para detecção de movimento"""
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # Configurações de detecção
        motion_threshold = 5000  # Sensibilidade
        min_motion_frames = 3    # Frames mínimos para confirmar movimento
        motion_frames = 0
        last_frame = None
        
        # Conectar ao stream
        cap = cv2.VideoCapture(camera.stream_url)
        if not cap.isOpened():
            print(f"Não foi possível conectar ao stream da câmera {camera.name}")
            return
        
        print(f"Iniciando detecção de movimento para {camera.name}")
        
        while motion_detection_active.get(camera_id, False):
            ret, frame = cap.read()
            if not ret:
                continue
            
            # Converter para escala de cinza
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            if last_frame is None:
                last_frame = gray
                continue
            
            # Calcular diferença entre frames
            frame_delta = cv2.absdiff(last_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            
            # Dilatar para preencher buracos
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Verificar movimento
            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) > motion_threshold:
                    motion_detected = True
                    break
            
            if motion_detected:
                motion_frames += 1
                if motion_frames >= min_motion_frames:
                    # Movimento confirmado - iniciar gravação
                    print(f"Movimento detectado em {camera.name}!")
                    start_recording.delay(camera_id)
                    motion_frames = 0
            else:
                motion_frames = 0
            
            last_frame = gray
            
            # Pequena pausa para não sobrecarregar
            time.sleep(0.1)
        
        cap.release()
        print(f"Detecção de movimento parada para {camera.name}")
        
    except Exception as e:
        print(f"Erro na detecção de movimento para câmera {camera_id}: {e}")
        motion_detection_active[camera_id] = False


@shared_task
def start_recording(camera_id):
    """Inicia gravação para uma câmera"""
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # Verificar se já está gravando
        if camera_id in recording_threads and recording_threads[camera_id]['active']:
            return f"Já gravando {camera.name}"
        
        # Criar diretório de gravações se não existir
        recordings_dir = os.path.join('recordings', 'videos', str(camera_id))
        os.makedirs(recordings_dir, exist_ok=True)
        
        # Nome do arquivo
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"motion_{timestamp}.mp4"
        filepath = os.path.join(recordings_dir, filename)
        
        # Criar registro de gravação
        recording = Recording.objects.create(
            camera=camera,
            file_path=filepath,
            file_name=filename,
            recording_type='motion',
            motion_detected=True
        )
        
        # Criar evento de movimento
        motion_event = MotionEvent.objects.create(
            camera=camera,
            recording=recording,
            confidence=0.8,
            area_affected=1000
        )
        
        # Iniciar thread de gravação
        recording_threads[camera_id] = {
            'active': True,
            'stop': False,
            'recording': recording,
            'motion_event': motion_event
        }
        
        thread = threading.Thread(
            target=recording_worker,
            args=(camera_id, filepath),
            daemon=True
        )
        thread.start()
        
        print(f"Gravação iniciada: {filepath}")
        return f"Gravação iniciada para {camera.name}"
        
    except Camera.DoesNotExist:
        return f"Câmera {camera_id} não encontrada"


def recording_worker(camera_id, filepath):
    """Worker para gravação de vídeo"""
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # Conectar ao stream
        cap = cv2.VideoCapture(camera.stream_url)
        if not cap.isOpened():
            print(f"Não foi possível conectar ao stream da câmera {camera.name}")
            return
        
        # Configurar codec
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
        
        start_time = time.time()
        frame_count = 0
        
        print(f"Iniciando gravação para {camera.name}")
        
        while recording_threads[camera_id]['active'] and not recording_threads[camera_id]['stop']:
            ret, frame = cap.read()
            if not ret:
                continue
            
            out.write(frame)
            frame_count += 1
            
            # Parar após 30 segundos ou se não há mais movimento
            if time.time() - start_time > 30:
                break
            
            time.sleep(0.01)  # Pequena pausa
        
        # Finalizar gravação
        out.release()
        cap.release()
        
        # Atualizar registro
        recording = recording_threads[camera_id]['recording']
        recording.end_time = timezone.now()
        recording.duration = int(time.time() - start_time)
        recording.file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        recording.save()
        
        # Finalizar evento de movimento
        motion_event = recording_threads[camera_id]['motion_event']
        motion_event.end_event()
        
        # Limpar thread
        recording_threads[camera_id]['active'] = False
        del recording_threads[camera_id]
        
        print(f"Gravação finalizada: {filepath}")
        
    except Exception as e:
        print(f"Erro na gravação para câmera {camera_id}: {e}")
        if camera_id in recording_threads:
            recording_threads[camera_id]['active'] = False


@shared_task
def start_motion_detection_all():
    """Inicia detecção de movimento para todas as câmeras online"""
    cameras = Camera.objects.filter(status='online', is_active=True)
    for camera in cameras:
        start_motion_detection.delay(str(camera.id))
    
    return f"Detecção iniciada para {cameras.count()} câmeras"


@shared_task
def stop_motion_detection_all():
    """Para detecção de movimento para todas as câmeras"""
    cameras = Camera.objects.filter(status='online', is_active=True)
    for camera in cameras:
        stop_motion_detection.delay(str(camera.id))
    
    return f"Detecção parada para {cameras.count()} câmeras" 