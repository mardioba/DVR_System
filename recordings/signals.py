import os
import subprocess
import threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Recording


@receiver(post_save, sender=Recording)
def trigger_video_conversion(sender, instance, created, **kwargs):
    """
    Signal que dispara a conversão de vídeo para H.264 quando uma gravação é finalizada
    """
    # Só processar se a gravação foi finalizada (tem end_time) e não foi convertida ainda
    if (instance.end_time and 
        instance.file_path and 
        os.path.exists(instance.file_path) and
        instance.conversion_status == 'pending'):
        
        # Iniciar conversão em thread separada para não bloquear
        thread = threading.Thread(
            target=convert_video_to_h264,
            args=(instance.id,),
            daemon=True
        )
        thread.start()
        print(f"🔄 Iniciando conversão para H.264: {instance.file_name}")


def convert_video_to_h264(recording_id):
    """
    Converte um vídeo para H.264 usando ffmpeg
    """
    try:
        # Buscar a gravação
        recording = Recording.objects.get(id=recording_id)
        
        # Atualizar status para convertendo
        recording.conversion_status = 'converting'
        recording.save()
        
        # Caminhos dos arquivos
        original_file = recording.file_path
        converted_dir = os.path.dirname(original_file)
        original_name = os.path.splitext(recording.file_name)[0]
        converted_name = f"{original_name}_h264.mp4"
        converted_file = os.path.join(converted_dir, converted_name)
        
        print(f"🔄 Convertendo {recording.file_name} para H.264...")
        
        # Comando ffmpeg para conversão
        cmd = [
            'ffmpeg',
            '-i', original_file,  # Arquivo de entrada
            '-c:v', 'libx264',    # Codec de vídeo H.264
            '-preset', 'medium',   # Preset de compressão (balanceado)
            '-crf', '23',         # Qualidade (18-28 é bom, menor = melhor qualidade)
            '-c:a', 'aac',        # Codec de áudio AAC
            '-b:a', '128k',       # Bitrate de áudio
            '-movflags', '+faststart',  # Otimizar para streaming
            '-y',                 # Sobrescrever arquivo se existir
            converted_file
        ]
        
        # Executar conversão
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # Timeout de 5 minutos
        )
        
        if result.returncode == 0 and os.path.exists(converted_file):
            # Conversão bem-sucedida
            file_size = os.path.getsize(converted_file)
            
            # Atualizar registro no banco
            recording.converted_file_path = converted_file
            recording.converted_file_name = converted_name
            recording.converted_file_size = file_size
            recording.conversion_status = 'completed'
            recording.conversion_error = None
            recording.save()
            
            print(f"✅ Conversão concluída: {converted_name} ({file_size / (1024*1024):.1f} MB)")
            
        else:
            # Erro na conversão
            error_msg = result.stderr if result.stderr else "Erro desconhecido na conversão"
            recording.conversion_status = 'failed'
            recording.conversion_error = error_msg
            recording.save()
            
            print(f"❌ Erro na conversão: {error_msg}")
            
    except subprocess.TimeoutExpired:
        # Timeout na conversão
        recording.conversion_status = 'failed'
        recording.conversion_error = "Timeout na conversão (5 minutos)"
        recording.save()
        print(f"❌ Timeout na conversão: {recording.file_name}")
        
    except Exception as e:
        # Erro geral
        try:
            recording.conversion_status = 'failed'
            recording.conversion_error = str(e)
            recording.save()
        except:
            pass
        print(f"❌ Erro na conversão: {e}")


def check_ffmpeg_available():
    """
    Verifica se o ffmpeg está disponível no sistema
    """
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_conversion_status():
    """
    Retorna estatísticas de conversão
    """
    total = Recording.objects.count()
    pending = Recording.objects.filter(conversion_status='pending').count()
    converting = Recording.objects.filter(conversion_status='converting').count()
    completed = Recording.objects.filter(conversion_status='completed').count()
    failed = Recording.objects.filter(conversion_status='failed').count()
    
    return {
        'total': total,
        'pending': pending,
        'converting': converting,
        'completed': completed,
        'failed': failed,
        'ffmpeg_available': check_ffmpeg_available()
    } 