from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
import os
import cv2
import ffmpeg
import threading
import time
import logging
import subprocess

from .models import Recording, RecordingSettings, MotionEvent
from cameras.models import Camera
from .utils import convert_recording, batch_convert_recordings, cleanup_converted_files

logger = logging.getLogger(__name__)


@shared_task
def start_motion_recording(camera_id):
    """Inicia gravação por detecção de movimento"""
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # Verificar se a câmera está ativa e tem gravação habilitada
        if not camera.is_active or not camera.recording_enabled:
            print(f"❌ Câmera {camera.name} não está ativa ou gravação desabilitada")
            return False
        
        # Obter configurações da câmera
        try:
            camera_settings = camera.settings
        except:
            camera_settings = None
        
        # Configurações padrão se não existir
        recording_duration = getattr(camera_settings, 'recording_duration', 30)
        frame_rate = getattr(camera_settings, 'frame_rate', 15)
        
        # Criar estrutura de diretórios
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"motion_{timestamp}.mp4"
        
        # Usar estrutura: recordings/videos/{camera_id}/{filename}
        camera_dir = os.path.join(settings.DVR_SETTINGS['RECORDINGS_PATH'], 'videos', str(camera.id))
        os.makedirs(camera_dir, exist_ok=True)
        
        filepath = os.path.join(camera_dir, filename)
        
        # Configurar gravação com FFmpeg
        stream_url = camera.get_stream_url()
        
        print(f"🎬 Iniciando gravação por movimento: {filename}")
        print(f"📁 Caminho: {filepath}")
        print(f"🔗 Stream: {stream_url}")
        print(f"⏱️ Duração: {recording_duration}s")
        
        try:
            # Usar subprocess diretamente para melhor controle
            import subprocess
            
            # Comando FFmpeg para gravação com configurações mais robustas
            cmd = [
                'ffmpeg',
                '-i', stream_url,
                '-c:v', 'libx264',  # Usar H.264 diretamente
                '-c:a', 'aac',
                '-r', str(frame_rate),
                '-preset', 'ultrafast',  # Codificação mais rápida
                '-crf', '25',  # Qualidade um pouco menor para estabilidade
                '-f', 'mp4',
                '-t', str(recording_duration),
                '-avoid_negative_ts', 'make_zero',  # Evitar timestamps negativos
                '-fflags', '+genpts',  # Gerar timestamps
                '-movflags', '+faststart',  # Otimizar para streaming
                '-y',  # Sobrescrever arquivo
                filepath
            ]
            
            # Executar gravação com timeout maior
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=recording_duration + 30  # Timeout maior que a duração
            )
            
            # Verificar se o arquivo foi criado e tem tamanho adequado
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                print(f"📊 Arquivo criado: {file_size} bytes")
                
                # Verificar se o arquivo tem tamanho mínimo (pelo menos 1KB)
                if file_size > 1024:
                    print(f"✅ Gravação bem-sucedida: {filename} ({file_size} bytes)")
                    
                    # Criar registro da gravação
                    recording = Recording.objects.create(
                        camera=camera,
                        file_path=filepath,
                        file_name=filename,
                        file_size=file_size,
                        duration=recording_duration,
                        recording_type='motion',
                        motion_detected=True,
                        end_time=timezone.now()
                    )
                    
                    # Criar evento de movimento
                    MotionEvent.objects.create(
                        camera=camera,
                        recording=recording,
                        duration=recording_duration,
                        confidence=0.8,  # Valor padrão
                        area_affected=1000  # Valor padrão
                    )
                    
                    return True
                else:
                    print(f"❌ Arquivo muito pequeno: {file_size} bytes")
                    # Remover arquivo pequeno
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    return False
            else:
                print(f"❌ Arquivo não foi criado")
                if result.stderr:
                    print(f"Erro FFmpeg: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout na gravação: {filename}")
            # Remover arquivo se foi criado
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
            return False
        except Exception as e:
            print(f"❌ Erro na gravação: {filename} - {e}")
            # Remover arquivo se foi criado
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
            return False
            
    except Camera.DoesNotExist:
        print(f"❌ Câmera {camera_id} não encontrada")
        return False
    except Exception as e:
        print(f"❌ Erro geral na gravação por movimento: {e}")
        return False


@shared_task
def start_manual_recording(camera_id, duration=30):
    """Inicia gravação manual"""
    try:
        camera = Camera.objects.get(id=camera_id)
        
        # Verificar se a câmera está ativa
        if not camera.is_active:
            print(f"❌ Câmera {camera.name} não está ativa")
            return False
        
        # Obter configurações da câmera
        try:
            camera_settings = camera.settings
            frame_rate = camera_settings.frame_rate
        except:
            frame_rate = 15
        
        # Criar estrutura de diretórios
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_{timestamp}.mp4"
        
        # Usar estrutura: recordings/videos/{camera_id}/{filename}
        camera_dir = os.path.join(settings.DVR_SETTINGS['RECORDINGS_PATH'], 'videos', str(camera.id))
        os.makedirs(camera_dir, exist_ok=True)
        
        filepath = os.path.join(camera_dir, filename)
        
        # Configurar gravação com FFmpeg
        stream_url = camera.get_stream_url()
        
        print(f"🎬 Iniciando gravação manual: {filename}")
        print(f"📁 Caminho: {filepath}")
        print(f"🔗 Stream: {stream_url}")
        print(f"⏱️ Duração: {duration}s")
        
        try:
            # Usar subprocess diretamente para melhor controle
            import subprocess
            
            # Comando FFmpeg para gravação com configurações mais robustas
            cmd = [
                'ffmpeg',
                '-i', stream_url,
                '-c:v', 'libx264',  # Usar H.264 diretamente
                '-c:a', 'aac',
                '-r', str(frame_rate),
                '-preset', 'ultrafast',  # Codificação mais rápida
                '-crf', '25',  # Qualidade um pouco menor para estabilidade
                '-f', 'mp4',
                '-t', str(duration),
                '-avoid_negative_ts', 'make_zero',  # Evitar timestamps negativos
                '-fflags', '+genpts',  # Gerar timestamps
                '-movflags', '+faststart',  # Otimizar para streaming
                '-y',  # Sobrescrever arquivo
                filepath
            ]
            
            # Executar gravação com timeout maior
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=duration + 30  # Timeout maior que a duração
            )
            
            # Verificar se o arquivo foi criado e tem tamanho adequado
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                print(f"📊 Arquivo criado: {file_size} bytes")
                
                # Verificar se o arquivo tem tamanho mínimo (pelo menos 1KB)
                if file_size > 1024:
                    print(f"✅ Gravação manual bem-sucedida: {filename} ({file_size} bytes)")
                    
                    # Criar registro da gravação
                    Recording.objects.create(
                        camera=camera,
                        file_path=filepath,
                        file_name=filename,
                        file_size=file_size,
                        duration=duration,
                        recording_type='manual',
                        motion_detected=False,
                        end_time=timezone.now()
                    )
                    
                    return True
                else:
                    print(f"❌ Arquivo muito pequeno: {file_size} bytes")
                    # Remover arquivo pequeno
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    return False
            else:
                print(f"❌ Arquivo não foi criado")
                if result.stderr:
                    print(f"Erro FFmpeg: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout na gravação manual: {filename}")
            # Remover arquivo se foi criado
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
            return False
        except Exception as e:
            print(f"❌ Erro na gravação manual: {filename} - {e}")
            # Remover arquivo se foi criado
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
            return False
            
    except Camera.DoesNotExist:
        print(f"❌ Câmera {camera_id} não encontrada")
        return False
    except Exception as e:
        print(f"❌ Erro geral na gravação manual: {e}")
        return False


@shared_task
def convert_pending_recordings():
    """Converte gravações pendentes automaticamente"""
    try:
        # Buscar gravações pendentes de conversão
        pending_recordings = Recording.objects.filter(
            conversion_status='pending',
            is_deleted=False
        ).order_by('start_time')[:5]  # Limitar a 5 por vez
        
        if not pending_recordings:
            logger.info("Nenhuma gravação pendente de conversão")
            return {"converted": 0, "errors": 0}
        
        logger.info(f"Iniciando conversão de {pending_recordings.count()} gravações")
        
        converted_count = 0
        error_count = 0
        
        for recording in pending_recordings:
            try:
                result = convert_recording(str(recording.id), quality='medium')
                if result['success']:
                    converted_count += 1
                    logger.info(f"✅ Gravação convertida: {recording.file_name}")
                else:
                    error_count += 1
                    logger.error(f"❌ Erro na conversão: {recording.file_name} - {result['error']}")
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Exceção na conversão: {recording.file_name} - {e}")
        
        logger.info(f"Conversão concluída: {converted_count} sucessos, {error_count} erros")
        return {"converted": converted_count, "errors": error_count}
        
    except Exception as e:
        logger.error(f"Erro na tarefa de conversão: {e}")
        return {"converted": 0, "errors": 1}


@shared_task
def retry_failed_conversions():
    """Tenta converter novamente gravações que falharam"""
    try:
        # Buscar gravações com erro na conversão
        failed_recordings = Recording.objects.filter(
            conversion_status='failed',
            is_deleted=False
        ).order_by('-start_time')[:3]  # Limitar a 3 por vez
        
        if not failed_recordings:
            logger.info("Nenhuma gravação com erro de conversão")
            return {"retried": 0, "errors": 0}
        
        logger.info(f"Tentando converter novamente {failed_recordings.count()} gravações")
        
        retried_count = 0
        error_count = 0
        
        for recording in failed_recordings:
            try:
                # Resetar status para pending
                recording.conversion_status = 'pending'
                recording.conversion_error = None
                recording.save()
                
                result = convert_recording(str(recording.id), quality='medium')
                if result['success']:
                    retried_count += 1
                    logger.info(f"✅ Gravação reconvertida: {recording.file_name}")
                else:
                    error_count += 1
                    logger.error(f"❌ Erro na reconversão: {recording.file_name} - {result['error']}")
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Exceção na reconversão: {recording.file_name} - {e}")
        
        logger.info(f"Reconversão concluída: {retried_count} sucessos, {error_count} erros")
        return {"retried": retried_count, "errors": error_count}
        
    except Exception as e:
        logger.error(f"Erro na tarefa de reconversão: {e}")
        return {"retried": 0, "errors": 1}


@shared_task
def cleanup_old_recordings():
    """Remove gravações antigas baseado nas configurações"""
    try:
        settings_obj = RecordingSettings.get_settings()
        
        if not settings_obj.auto_delete_enabled:
            logger.info("Exclusão automática desabilitada")
            return {"deleted": 0}
        
        # Calcular data limite
        cutoff_date = timezone.now() - timedelta(days=settings_obj.max_recording_days)
        
        # Buscar gravações antigas
        old_recordings = Recording.objects.filter(
            start_time__lt=cutoff_date,
            is_deleted=False
        )
        
        if not old_recordings:
            logger.info("Nenhuma gravação antiga encontrada")
            return {"deleted": 0}
        
        logger.info(f"Removendo {old_recordings.count()} gravações antigas")
        
        deleted_count = 0
        for recording in old_recordings:
            try:
                if recording.delete_file():
                    recording.is_deleted = True
                    recording.save()
                    deleted_count += 1
                    logger.info(f"🗑️ Gravação removida: {recording.file_name}")
                else:
                    logger.error(f"❌ Erro ao remover arquivo: {recording.file_name}")
            except Exception as e:
                logger.error(f"❌ Exceção ao remover: {recording.file_name} - {e}")
        
        logger.info(f"Limpeza concluída: {deleted_count} gravações removidas")
        return {"deleted": deleted_count}
        
    except Exception as e:
        logger.error(f"Erro na tarefa de limpeza: {e}")
        return {"deleted": 0}


@shared_task
def cleanup_orphaned_files():
    """Remove arquivos convertidos órfãos"""
    try:
        cleaned_count = cleanup_converted_files()
        logger.info(f"Limpeza de arquivos órfãos: {cleaned_count} arquivos removidos")
        return {"cleaned": cleaned_count}
    except Exception as e:
        logger.error(f"Erro na limpeza de arquivos órfãos: {e}")
        return {"cleaned": 0}


@shared_task
def check_storage_usage():
    """Verifica o uso de armazenamento e alerta se necessário"""
    try:
        settings_obj = RecordingSettings.get_settings()
        
        # Calcular uso atual
        total_size = Recording.objects.filter(is_deleted=False).aggregate(
            total_size=models.Sum('file_size')
        )['total_size'] or 0
        
        total_size_gb = total_size / (1024**3)
        limit_gb = settings_obj.storage_limit_gb
        
        usage_percent = (total_size_gb / limit_gb) * 100 if limit_gb > 0 else 0
        
        logger.info(f"Uso de armazenamento: {total_size_gb:.2f}GB / {limit_gb}GB ({usage_percent:.1f}%)")
        
        # Alertar se uso > 80%
        if usage_percent > 80:
            logger.warning(f"⚠️ Uso de armazenamento alto: {usage_percent:.1f}%")
            
            # Se > 90%, forçar limpeza
            if usage_percent > 90:
                logger.warning("🚨 Uso crítico de armazenamento, forçando limpeza")
                cleanup_old_recordings.delay()
        
        return {
            "total_gb": total_size_gb,
            "limit_gb": limit_gb,
            "usage_percent": usage_percent
        }
        
    except Exception as e:
        logger.error(f"Erro na verificação de armazenamento: {e}")
        return {"error": str(e)}


@shared_task
def convert_specific_recording(recording_id, quality='medium'):
    """Converte uma gravação específica"""
    try:
        result = convert_recording(recording_id, quality)
        
        if result['success']:
            logger.info(f"✅ Conversão concluída: {recording_id}")
        else:
            logger.error(f"❌ Erro na conversão: {recording_id} - {result['error']}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Exceção na conversão: {recording_id} - {e}")
        return {"success": False, "error": str(e)}


@shared_task
def batch_convert_specific_recordings(recording_ids, quality='medium'):
    """Converte múltiplas gravações específicas"""
    try:
        result = batch_convert_recordings(recording_ids, quality)
        
        logger.info(f"Conversão em lote: {result['success']} sucessos, {result['failed']} falhas")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Exceção na conversão em lote: {e}")
        return {"success": 0, "failed": len(recording_ids), "errors": [str(e)]}


@shared_task
def update_camera_status():
    """Atualiza status das câmeras verificando conectividade"""
    try:
        cameras = Camera.objects.filter(is_active=True)
        
        for camera in cameras:
            try:
                # Tentar conectar com a câmera
                cap = cv2.VideoCapture(camera.get_stream_url())
                
                if cap.isOpened():
                    camera.update_status('online')
                    cap.release()
                else:
                    camera.update_status('offline')
                    
            except Exception as e:
                camera.update_status('error')
                print(f"Erro ao verificar câmera {camera.name}: {e}")
        
        return True
        
    except Exception as e:
        print(f"Erro na atualização de status das câmeras: {e}")
        return False 