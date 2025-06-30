import cv2
import numpy as np
import threading
import time
import os
from datetime import datetime
from django.conf import settings
import ffmpeg


class MotionDetector:
    """Classe para detecção de movimento em streams de vídeo"""
    
    def __init__(self, sensitivity=0.3, min_area=500):
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=100, varThreshold=50, detectShadows=False
        )
        self.previous_frame = None
        self.motion_detected = False
        self.motion_start_time = None
        self.motion_timeout = 4  # segundos
        self.motion_start_delay = 10  # segundos
        
    def detect_motion(self, frame):
        """Detecta movimento em um frame"""
        # Converter para escala de cinza
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Se não temos frame anterior, usar o atual
        if self.previous_frame is None:
            self.previous_frame = gray
            return False
        
        # Calcular diferença entre frames
        frame_delta = cv2.absdiff(self.previous_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        # Dilatar a imagem para preencher buracos
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Verificar se há movimento significativo
        motion_detected = False
        for contour in contours:
            if cv2.contourArea(contour) > self.min_area:
                motion_detected = True
                break
        
        # Atualizar estado de movimento
        current_time = time.time()
        
        if motion_detected:
            if not self.motion_detected:
                self.motion_start_time = current_time
                self.motion_detected = True
        else:
            # Se não há movimento e já estava detectando, verificar timeout
            if self.motion_detected and self.motion_start_time:
                if current_time - self.motion_start_time > self.motion_timeout:
                    self.motion_detected = False
                    self.motion_start_time = None
        
        # Atualizar frame anterior
        self.previous_frame = gray
        
        return self.motion_detected
    
    def should_start_recording(self):
        """Verifica se deve iniciar gravação baseado no delay"""
        if self.motion_detected and self.motion_start_time:
            return time.time() - self.motion_start_time >= self.motion_start_delay
        return False


class StreamProcessor:
    """Classe para processamento de streams de vídeo"""
    
    def __init__(self, camera, settings):
        self.camera = camera
        self.settings = settings
        self.motion_detector = MotionDetector(
            sensitivity=settings.motion_sensitivity,
            min_area=1000
        )
        self.is_recording = False
        self.recording_thread = None
        self.stop_processing = False
        
    def start_processing(self):
        """Inicia o processamento do stream"""
        self.stop_processing = False
        self.processing_thread = threading.Thread(target=self._process_stream)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
    def stop_processing(self):
        """Para o processamento do stream"""
        self.stop_processing = True
        if self.is_recording:
            self.stop_recording()
        
    def _process_stream(self):
        """Processa o stream em loop"""
        cap = cv2.VideoCapture(self.camera.get_stream_url())
        
        if not cap.isOpened():
            print(f"Erro ao abrir stream da câmera {self.camera.name}")
            return
        
        try:
            while not self.stop_processing:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Detectar movimento
                motion_detected = self.motion_detector.detect_motion(frame)
                
                # Verificar se deve iniciar gravação
                if motion_detected and self.motion_detector.should_start_recording():
                    if not self.is_recording:
                        self.start_recording()
                
                # Verificar se deve parar gravação
                if not motion_detected and self.is_recording:
                    self.stop_recording()
                
                # Pequena pausa para não sobrecarregar
                time.sleep(0.1)
                
        finally:
            cap.release()
    
    def start_recording(self):
        """Inicia gravação do stream"""
        if self.is_recording:
            return
        
        self.is_recording = True
        self.recording_thread = threading.Thread(target=self._record_stream)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        print(f"Iniciando gravação da câmera {self.camera.name}")
    
    def stop_recording(self):
        """Para gravação do stream"""
        self.is_recording = False
        print(f"Parando gravação da câmera {self.camera.name}")
    
    def _record_stream(self):
        """Grava o stream em arquivo"""
        # Criar nome do arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.camera.name}_{timestamp}.mp4"
        filepath = os.path.join(settings.DVR_SETTINGS['RECORDINGS_PATH'], filename)
        
        # Configurar FFmpeg para gravação
        try:
            stream_url = self.camera.get_stream_url()
            
            # Configurações de gravação
            input_stream = ffmpeg.input(stream_url)
            
            # Configurar codec e qualidade
            output_stream = ffmpeg.output(
                input_stream,
                filepath,
                vcodec=settings.DVR_SETTINGS['VIDEO_CODEC'],
                acodec=settings.DVR_SETTINGS['AUDIO_CODEC'],
                r=settings.DVR_SETTINGS['FRAME_RATE'],
                preset='fast',
                crf=23,  # Qualidade
                f='mp4'
            )
            
            # Iniciar gravação
            process = ffmpeg.run_async(output_stream)
            
            # Aguardar até parar gravação ou timeout
            start_time = time.time()
            while self.is_recording:
                if time.time() - start_time > self.settings.recording_duration:
                    break
                time.sleep(1)
            
            # Parar gravação
            process.terminate()
            process.wait()
            
            # Salvar registro da gravação
            from recordings.models import Recording
            Recording.objects.create(
                camera=self.camera,
                file_path=filepath,
                file_size=os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                duration=self.settings.recording_duration,
                recording_type='motion',
                motion_detected=True
            )
            
        except Exception as e:
            print(f"Erro na gravação da câmera {self.camera.name}: {e}")


class ONVIFDiscovery:
    """Classe para descoberta de câmeras ONVIF"""
    
    def __init__(self):
        self.discovered_cameras = []
    
    def discover_cameras(self):
        """Descobre câmeras ONVIF na rede"""
        try:
            from wsdiscovery import WSDiscovery
            from onvif import ONVIFCamera
            
            wsd = WSDiscovery()
            wsd.start()
            
            # Procurar por dispositivos ONVIF
            services = wsd.searchServices()
            
            for service in services:
                try:
                    # Tentar conectar via ONVIF
                    service_url = service.getXAddrs()[0]
                    ip_address = service_url.split('://')[1].split(':')[0]
                    
                    cam = ONVIFCamera(ip_address, 80, '', '')
                    
                    # Obter informações do dispositivo
                    device_info = cam.devicemgmt.GetDeviceInformation()
                    
                    # Obter configurações de mídia
                    media_service = cam.create_media_service()
                    profiles = media_service.GetProfiles()
                    
                    # Encontrar URL do stream RTSP
                    rtsp_url = None
                    for profile in profiles:
                        stream_uri = media_service.GetStreamUri({
                            'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}},
                            'ProfileToken': profile.token
                        })
                        rtsp_url = stream_uri.Uri
                        break
                    
                    camera_info = {
                        'ip_address': ip_address,
                        'manufacturer': device_info.Manufacturer,
                        'model': device_info.Model,
                        'serial_number': device_info.SerialNumber,
                        'firmware_version': device_info.FirmwareVersion,
                        'onvif_url': service_url,
                        'rtsp_url': rtsp_url,
                    }
                    
                    self.discovered_cameras.append(camera_info)
                    
                except Exception as e:
                    print(f"Erro ao conectar com câmera ONVIF {ip_address}: {e}")
                    continue
            
            wsd.stop()
            
        except Exception as e:
            print(f"Erro na descoberta de câmeras: {e}")
        
        return self.discovered_cameras 