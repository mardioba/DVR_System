import cv2
import threading
import time
import os
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from cameras.models import Camera
from recordings.models import Recording, MotionEvent
from recordings.tasks import start_motion_recording


class MotionDetector:
    """Sistema de detecção de movimento usando threads"""
    
    def __init__(self):
        self.detection_threads = {}
        self.recording_threads = {}
        self.running = False
        
    def start_detection_for_camera(self, camera_id):
        """Inicia detecção de movimento para uma câmera específica"""
        if camera_id in self.detection_threads and self.detection_threads[camera_id]['running']:
            return f"Detecção já ativa para câmera {camera_id}"
        
        try:
            camera = Camera.objects.get(id=camera_id, is_active=True)
            
            # Criar thread de detecção
            thread = threading.Thread(
                target=self._detection_worker,
                args=(camera_id,),
                daemon=True
            )
            
            self.detection_threads[camera_id] = {
                'thread': thread,
                'running': True,
                'camera': camera
            }
            
            thread.start()
            print(f"✅ Detecção de movimento iniciada para {camera.name}")
            return f"Detecção iniciada para {camera.name}"
            
        except Camera.DoesNotExist:
            return f"Câmera {camera_id} não encontrada"
    
    def stop_detection_for_camera(self, camera_id):
        """Para detecção de movimento para uma câmera"""
        if camera_id in self.detection_threads:
            self.detection_threads[camera_id]['running'] = False
            print(f"🛑 Detecção de movimento parada para câmera {camera_id}")
            return f"Detecção parada para câmera {camera_id}"
        return f"Detecção não estava ativa para câmera {camera_id}"
    
    def start_detection_for_all_cameras(self):
        """Inicia detecção para todas as câmeras online"""
        cameras = Camera.objects.filter(status='online', is_active=True)
        started_count = 0
        
        for camera in cameras:
            result = self.start_detection_for_camera(str(camera.id))
            if "iniciada" in result:
                started_count += 1
        
        print(f"✅ Detecção iniciada para {started_count} câmeras")
        return f"Detecção iniciada para {started_count} câmeras"
    
    def stop_detection_for_all_cameras(self):
        """Para detecção para todas as câmeras"""
        stopped_count = 0
        
        for camera_id in list(self.detection_threads.keys()):
            result = self.stop_detection_for_camera(camera_id)
            if "parada" in result:
                stopped_count += 1
        
        print(f"🛑 Detecção parada para {stopped_count} câmeras")
        return f"Detecção parada para {stopped_count} câmeras"
    
    def _detection_worker(self, camera_id):
        """Worker para detecção de movimento"""
        try:
            camera = self.detection_threads[camera_id]['camera']
            
            # Configurações de detecção
            motion_threshold = 3000  # Sensibilidade (menor = mais sensível)
            min_motion_frames = 2    # Frames mínimos para confirmar movimento
            motion_frames = 0
            last_frame = None
            retry_count = 0
            max_retries = 3
            last_recording_time = 0
            min_recording_interval = 10  # Reduzido para 10 segundos entre gravações
            
            print(f"🎥 Iniciando detecção para {camera.name} - {camera.stream_url}")
            
            while self.detection_threads.get(camera_id, {}).get('running', False):
                try:
                    # Conectar ao stream
                    cap = cv2.VideoCapture(camera.stream_url)
                    if not cap.isOpened():
                        print(f"❌ Não foi possível conectar ao stream da câmera {camera.name}")
                        retry_count += 1
                        if retry_count >= max_retries:
                            print(f"🛑 Máximo de tentativas atingido para {camera.name}")
                            break
                        time.sleep(5)  # Esperar 5 segundos antes de tentar novamente
                        continue
                    
                    # Configurar timeouts
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000)
                    
                    print(f"✅ Conectado ao stream da câmera {camera.name}")
                    retry_count = 0  # Resetar contador de tentativas
                    
                    # Loop de detecção
                    while self.detection_threads.get(camera_id, {}).get('running', False):
                        ret, frame = cap.read()
                        if not ret:
                            print(f"⚠️ Erro ao ler frame da câmera {camera.name}")
                            break
                        
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
                                # Verificar se passou tempo suficiente desde a última gravação
                                current_time = time.time()
                                if current_time - last_recording_time >= min_recording_interval:
                                    # Movimento confirmado - iniciar gravação via Celery
                                    print(f"🚨 MOVIMENTO DETECTADO em {camera.name}!")
                                    self._start_recording(camera_id)
                                    last_recording_time = current_time
                                    motion_frames = 0
                                    time.sleep(2)  # Pausa para evitar múltiplas gravações
                                else:
                                    remaining_time = min_recording_interval - (current_time - last_recording_time)
                                    print(f"⏰ Movimento detectado em {camera.name} - Aguardando {remaining_time:.1f}s para próxima gravação")
                                    motion_frames = 0
                        else:
                            motion_frames = 0
                        
                        last_frame = gray
                        time.sleep(0.1)  # Pequena pausa
                    
                    cap.release()
                    
                except Exception as e:
                    print(f"❌ Erro na detecção para câmera {camera.name}: {e}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"🛑 Máximo de tentativas atingido para {camera.name}")
                        break
                    time.sleep(5)  # Esperar antes de tentar novamente
                    
            print(f"🛑 Detecção finalizada para {camera.name}")
            
        except Exception as e:
            print(f"❌ Erro fatal na detecção para câmera {camera_id}: {e}")
        finally:
            if camera_id in self.detection_threads:
                self.detection_threads[camera_id]['running'] = False
    
    def _start_recording(self, camera_id):
        """Inicia gravação para uma câmera diretamente"""
        try:
            camera = self.detection_threads[camera_id]['camera']
            
            # Verificar se já está gravando
            if camera_id in self.recording_threads and self.recording_threads[camera_id]['running']:
                print(f"📹 Já gravando {camera.name}")
                return
            
            # Marcar como gravando
            self.recording_threads[camera_id] = {
                'running': True,
                'start_time': time.time()
            }
            
            # Iniciar gravação diretamente
            print(f"📹 Iniciando gravação por movimento diretamente para {camera.name}")
            try:
                # Executar gravação diretamente
                result = start_motion_recording(camera_id)
                print(f"✅ Gravação iniciada diretamente: {result}")
            except Exception as direct_error:
                print(f"❌ Erro na gravação direta: {direct_error}")
                if camera_id in self.recording_threads:
                    self.recording_threads[camera_id]['running'] = False
                return
            
            # Limpar flag de gravação após um tempo
            def clear_recording_flag():
                time.sleep(15)  # Reduzido para 15 segundos (um pouco mais que a duração da gravação)
                if camera_id in self.recording_threads:
                    self.recording_threads[camera_id]['running'] = False
            
            # Executar limpeza em thread separada
            cleanup_thread = threading.Thread(target=clear_recording_flag, daemon=True)
            cleanup_thread.start()
            
        except Exception as e:
            print(f"❌ Erro ao iniciar gravação para câmera {camera_id}: {e}")
            if camera_id in self.recording_threads:
                self.recording_threads[camera_id]['running'] = False


# Instância global do detector
motion_detector = MotionDetector()


def start_motion_detection():
    """Função para iniciar detecção de movimento"""
    return motion_detector.start_detection_for_all_cameras()


def stop_motion_detection():
    """Função para parar detecção de movimento"""
    return motion_detector.stop_detection_for_all_cameras()


def get_detection_status():
    """Retorna status da detecção de movimento"""
    active_cameras = []
    for camera_id, data in motion_detector.detection_threads.items():
        if data['running']:
            active_cameras.append(data['camera'].name)
    
    return {
        'active_cameras': active_cameras,
        'total_active': len(active_cameras),
        'recording_cameras': len([c for c in motion_detector.recording_threads.values() if c['running']])
    } 