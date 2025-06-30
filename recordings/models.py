from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid
import os


class Recording(models.Model):
    """Modelo para armazenar informações das gravações"""
    
    RECORDING_TYPES = [
        ('motion', 'Detecção de Movimento'),
        ('manual', 'Gravação Manual'),
        ('scheduled', 'Gravação Programada'),
        ('continuous', 'Gravação Contínua'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='recordings')
    file_path = models.CharField(max_length=500, verbose_name='Caminho do Arquivo')
    file_name = models.CharField(max_length=200, verbose_name='Nome do Arquivo')
    file_size = models.BigIntegerField(default=0, verbose_name='Tamanho do Arquivo (bytes)')
    duration = models.IntegerField(default=0, verbose_name='Duração (segundos)')
    recording_type = models.CharField(max_length=20, choices=RECORDING_TYPES, default='motion', verbose_name='Tipo de Gravação')
    motion_detected = models.BooleanField(default=False, verbose_name='Movimento Detectado')
    start_time = models.DateTimeField(auto_now_add=True, verbose_name='Hora de Início')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='Hora de Fim')
    is_deleted = models.BooleanField(default=False, verbose_name='Excluído')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    
    # Campos para conversão H.264
    converted_file_path = models.CharField(max_length=500, blank=True, null=True, verbose_name='Caminho do Arquivo Convertido')
    converted_file_name = models.CharField(max_length=200, blank=True, null=True, verbose_name='Nome do Arquivo Convertido')
    converted_file_size = models.BigIntegerField(default=0, verbose_name='Tamanho do Arquivo Convertido (bytes)')
    conversion_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pendente'),
        ('converting', 'Convertendo'),
        ('completed', 'Concluído'),
        ('failed', 'Falhou')
    ], default='pending', verbose_name='Status da Conversão')
    conversion_error = models.TextField(blank=True, null=True, verbose_name='Erro na Conversão')
    
    class Meta:
        verbose_name = 'Gravação'
        verbose_name_plural = 'Gravações'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.camera.name} - {self.start_time.strftime('%d/%m/%Y %H:%M')}"
    
    def save(self, *args, **kwargs):
        # Extrair nome do arquivo do caminho
        if self.file_path and not self.file_name:
            self.file_name = os.path.basename(self.file_path)
        
        # Calcular tamanho do arquivo se não foi informado
        if self.file_path and self.file_size == 0:
            try:
                if os.path.exists(self.file_path):
                    self.file_size = os.path.getsize(self.file_path)
            except:
                pass
        
        super().save(*args, **kwargs)
    
    def get_file_size_mb(self):
        """Retorna o tamanho do arquivo em MB"""
        return round(self.file_size / (1024 * 1024), 2)
    
    def get_converted_file_size_mb(self):
        """Retorna o tamanho do arquivo convertido em MB"""
        return round(self.converted_file_size / (1024 * 1024), 2)
    
    def get_duration_formatted(self):
        """Retorna a duração formatada"""
        if self.duration:
            minutes = self.duration // 60
            seconds = self.duration % 60
            return f"{minutes:02d}:{seconds:02d}"
        return "00:00"
    
    def get_file_url(self):
        """Retorna a URL para download do arquivo"""
        if self.file_path and os.path.exists(self.file_path):
            return f"/recordings/download/{self.id}/"
        return None
    
    def get_converted_file_url(self):
        """Retorna a URL para download do arquivo convertido"""
        if self.converted_file_path and os.path.exists(self.converted_file_path):
            return f"/recordings/download/{self.id}/converted/"
        return None
    
    @property
    def file_exists(self):
        """Verifica se o arquivo físico existe"""
        return self.file_path and os.path.exists(self.file_path)
    
    @property
    def converted_file_exists(self):
        """Verifica se o arquivo convertido existe"""
        return self.converted_file_path and os.path.exists(self.converted_file_path)
    
    @property
    def has_playable_video(self):
        """Verifica se existe um vídeo reproduzível (convertido ou original)"""
        return self.converted_file_exists or self.file_exists
    
    def delete_file(self):
        """Exclui o arquivo físico"""
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            if self.converted_file_path and os.path.exists(self.converted_file_path):
                os.remove(self.converted_file_path)
            return True
        except Exception as e:
            print(f"Erro ao excluir arquivo {self.file_path}: {e}")
        return False


class RecordingSettings(models.Model):
    """Configurações globais de gravação"""
    
    max_recording_days = models.IntegerField(default=30, verbose_name='Dias Máximos de Retenção')
    auto_delete_enabled = models.BooleanField(default=True, verbose_name='Exclusão Automática')
    storage_limit_gb = models.IntegerField(default=100, verbose_name='Limite de Armazenamento (GB)')
    compression_enabled = models.BooleanField(default=True, verbose_name='Compressão Habilitada')
    backup_enabled = models.BooleanField(default=False, verbose_name='Backup Habilitado')
    backup_path = models.CharField(max_length=500, blank=True, verbose_name='Caminho do Backup')
    
    class Meta:
        verbose_name = 'Configuração de Gravação'
        verbose_name_plural = 'Configurações de Gravação'
    
    def __str__(self):
        return 'Configurações Globais de Gravação'
    
    @classmethod
    def get_settings(cls):
        """Retorna as configurações globais, criando se não existir"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


class MotionEvent(models.Model):
    """Eventos de detecção de movimento"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    camera = models.ForeignKey('cameras.Camera', on_delete=models.CASCADE, related_name='motion_events')
    recording = models.ForeignKey(Recording, on_delete=models.CASCADE, related_name='motion_events', null=True, blank=True)
    start_time = models.DateTimeField(auto_now_add=True, verbose_name='Hora de Início')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='Hora de Fim')
    duration = models.IntegerField(default=0, verbose_name='Duração (segundos)')
    confidence = models.FloatField(default=0.0, verbose_name='Confiança da Detecção')
    area_affected = models.IntegerField(default=0, verbose_name='Área Afetada (pixels)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    
    class Meta:
        verbose_name = 'Evento de Movimento'
        verbose_name_plural = 'Eventos de Movimento'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.camera.name} - {self.start_time.strftime('%d/%m/%Y %H:%M:%S')}"
    
    def end_event(self):
        """Finaliza o evento de movimento"""
        self.end_time = timezone.now()
        if self.start_time:
            self.duration = int((self.end_time - self.start_time).total_seconds())
        self.save() 