import os
import subprocess
import logging
import json
from django.conf import settings
from django.utils import timezone
from .models import Recording

logger = logging.getLogger(__name__)


def convert_video_to_h264(input_path, output_path, quality='medium'):
    """
    Converte vídeo para H.264 usando FFmpeg
    
    Args:
        input_path: Caminho do arquivo de entrada
        output_path: Caminho do arquivo de saída
        quality: Qualidade da conversão ('low', 'medium', 'high')
    
    Returns:
        dict: Resultado da conversão com status e informações
    """
    
    # Verificar se o arquivo de entrada existe
    if not os.path.exists(input_path):
        return {
            'success': False,
            'error': f'Arquivo de entrada não encontrado: {input_path}'
        }
    
    # Verificar se FFmpeg está disponível
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {
            'success': False,
            'error': 'FFmpeg não está instalado ou não está disponível no PATH'
        }
    
    # Configurações de qualidade
    quality_settings = {
        'low': {
            'video_bitrate': '500k',
            'audio_bitrate': '64k',
            'resolution': '640x480'
        },
        'medium': {
            'video_bitrate': '1000k',
            'audio_bitrate': '128k',
            'resolution': '1280x720'
        },
        'high': {
            'video_bitrate': '2000k',
            'audio_bitrate': '192k',
            'resolution': '1920x1080'
        }
    }
    
    config = quality_settings.get(quality, quality_settings['medium'])
    
    # Comando FFmpeg para conversão
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-c:v', 'libx264',  # Codec de vídeo H.264
        '-preset', 'medium',  # Preset de codificação
        '-crf', '23',  # Constante Rate Factor (qualidade)
        '-b:v', config['video_bitrate'],  # Bitrate de vídeo
        '-c:a', 'aac',  # Codec de áudio AAC
        '-b:a', config['audio_bitrate'],  # Bitrate de áudio
        '-vf', f'scale={config["resolution"]}:force_original_aspect_ratio=decrease',  # Redimensionar
        '-movflags', '+faststart',  # Otimizar para streaming
        '-y',  # Sobrescrever arquivo de saída
        output_path
    ]
    
    try:
        # Executar conversão
        start_time = timezone.now()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # Timeout de 1 hora
        )
        end_time = timezone.now()
        
        if result.returncode == 0:
            # Verificar se o arquivo de saída foi criado
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                duration = (end_time - start_time).total_seconds()
                
                return {
                    'success': True,
                    'output_path': output_path,
                    'file_size': file_size,
                    'conversion_time': duration,
                    'original_size': os.path.getsize(input_path)
                }
            else:
                return {
                    'success': False,
                    'error': 'Arquivo de saída não foi criado'
                }
        else:
            return {
                'success': False,
                'error': f'Erro na conversão: {result.stderr}'
            }
            
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Conversão excedeu o tempo limite (1 hora)'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Erro inesperado: {str(e)}'
        }


def get_video_info(file_path):
    """
    Obtém informações do vídeo usando FFprobe
    
    Args:
        file_path: Caminho do arquivo de vídeo
    
    Returns:
        dict: Informações do vídeo
    """
    
    if not os.path.exists(file_path):
        return None
    
    try:
        # Comando FFprobe para obter informações
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        info = json.loads(result.stdout)
        
        # Extrair informações relevantes
        format_info = info.get('format', {})
        video_stream = next((s for s in info.get('streams', []) if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in info.get('streams', []) if s['codec_type'] == 'audio'), None)
        
        return {
            'duration': float(format_info.get('duration', 0)),
            'size': int(format_info.get('size', 0)),
            'bitrate': int(format_info.get('bit_rate', 0)),
            'format': format_info.get('format_name', ''),
            'video_codec': video_stream.get('codec_name', '') if video_stream else '',
            'video_resolution': f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}" if video_stream else '',
            'audio_codec': audio_stream.get('codec_name', '') if audio_stream else '',
            'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0
        }
        
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Erro ao obter informações do vídeo {file_path}: {e}")
        return None


def convert_recording(recording_id, quality='medium'):
    """
    Converte uma gravação específica para H.264
    
    Args:
        recording_id: ID da gravação
        quality: Qualidade da conversão
    
    Returns:
        dict: Resultado da conversão
    """
    
    try:
        recording = Recording.objects.get(id=recording_id)
    except Recording.DoesNotExist:
        return {
            'success': False,
            'error': 'Gravação não encontrada'
        }
    
    # Verificar se o arquivo original existe
    if not recording.file_exists:
        return {
            'success': False,
            'error': 'Arquivo original não encontrado'
        }
    
    # Verificar se já foi convertido
    if recording.conversion_status == 'completed' and recording.converted_file_exists:
        return {
            'success': True,
            'message': 'Arquivo já foi convertido',
            'output_path': recording.converted_file_path
        }
    
    # Atualizar status para convertendo
    recording.conversion_status = 'converting'
    recording.conversion_error = None
    recording.save()
    
    # Gerar caminho do arquivo convertido
    file_name = os.path.splitext(recording.file_name)[0]
    output_dir = os.path.join(settings.MEDIA_ROOT, 'recordings', 'converted')
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, f"{file_name}_converted.mp4")
    
    # Realizar conversão
    result = convert_video_to_h264(recording.file_path, output_path, quality)
    
    if result['success']:
        # Atualizar modelo com informações da conversão
        recording.converted_file_path = output_path
        recording.converted_file_name = os.path.basename(output_path)
        recording.converted_file_size = result['file_size']
        recording.conversion_status = 'completed'
        recording.conversion_error = None
        recording.save()
        
        logger.info(f"Conversão concluída: {recording.file_name} -> {recording.converted_file_name}")
        
        return {
            'success': True,
            'recording_id': recording.id,
            'output_path': output_path,
            'file_size': result['file_size'],
            'conversion_time': result['conversion_time']
        }
    else:
        # Atualizar status de erro
        recording.conversion_status = 'failed'
        recording.conversion_error = result['error']
        recording.save()
        
        logger.error(f"Erro na conversão: {recording.file_name} - {result['error']}")
        
        return result


def batch_convert_recordings(recording_ids, quality='medium'):
    """
    Converte múltiplas gravações em lote
    
    Args:
        recording_ids: Lista de IDs das gravações
        quality: Qualidade da conversão
    
    Returns:
        dict: Resultado do lote
    """
    
    results = {
        'total': len(recording_ids),
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for recording_id in recording_ids:
        try:
            result = convert_recording(recording_id, quality)
            if result['success']:
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'recording_id': recording_id,
                    'error': result['error']
                })
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'recording_id': recording_id,
                'error': str(e)
            })
    
    return results


def cleanup_converted_files():
    """
    Remove arquivos convertidos órfãos (sem registro no banco)
    """
    
    converted_dir = os.path.join(settings.MEDIA_ROOT, 'recordings', 'converted')
    if not os.path.exists(converted_dir):
        return
    
    # Obter todos os arquivos convertidos registrados
    recorded_files = set()
    for recording in Recording.objects.filter(converted_file_path__isnull=False):
        if recording.converted_file_path:
            recorded_files.add(os.path.basename(recording.converted_file_path))
    
    # Verificar arquivos físicos
    orphaned_files = []
    for filename in os.listdir(converted_dir):
        if filename.endswith('_converted.mp4') and filename not in recorded_files:
            file_path = os.path.join(converted_dir, filename)
            orphaned_files.append(file_path)
    
    # Remover arquivos órfãos
    for file_path in orphaned_files:
        try:
            os.remove(file_path)
            logger.info(f"Arquivo órfão removido: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao remover arquivo órfão {file_path}: {e}")
    
    return len(orphaned_files) 