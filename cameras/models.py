from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Camera(models.Model):
    """Modelo para armazenar informações das câmeras IP"""
    
    CAMERA_STATUS = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Erro'),
        ('disconnected', 'Desconectado'),
    ]
    
    CAMERA_TYPES = [
        ('rtsp', 'RTSP'),
        ('http', 'HTTP'),
        ('onvif', 'ONVIF'),
        ('rtmp', 'RTMP'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='Nome da Câmera')
    description = models.TextField(blank=True, verbose_name='Descrição')
    ip_address = models.GenericIPAddressField(verbose_name='Endereço IP')
    port = models.IntegerField(default=554, verbose_name='Porta')
    stream_url = models.CharField(max_length=500, verbose_name='URL do Stream')
    camera_type = models.CharField(max_length=10, choices=CAMERA_TYPES, default='rtsp', verbose_name='Tipo')
    username = models.CharField(max_length=50, blank=True, verbose_name='Usuário')
    password = models.CharField(max_length=100, blank=True, verbose_name='Senha')
    status = models.CharField(max_length=20, choices=CAMERA_STATUS, default='offline', verbose_name='Status')
    is_active = models.BooleanField(default=True, verbose_name='Ativa')
    motion_detection_enabled = models.BooleanField(default=True, verbose_name='Detecção de Movimento')
    recording_enabled = models.BooleanField(default=True, verbose_name='Gravação Habilitada')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Atualização')
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name='Última Conexão')
    
    class Meta:
        verbose_name = 'Câmera'
        verbose_name_plural = 'Câmeras'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_stream_url(self):
        """Retorna a URL completa do stream com autenticação se necessário"""
        # Se a URL já contém credenciais, retornar como está
        if '@' in self.stream_url:
            return self.stream_url
        
        # Se não tem credenciais na URL mas tem username/password, adicionar
        if self.username and self.password:
            if '://' in self.stream_url:
                protocol, rest = self.stream_url.split('://', 1)
                return f"{protocol}://{self.username}:{self.password}@{rest}"
        
        return self.stream_url
    
    def update_status(self, status):
        """Atualiza o status da câmera"""
        self.status = status
        if status == 'online':
            self.last_seen = timezone.now()
        self.save(update_fields=['status', 'last_seen'])


class CameraSettings(models.Model):
    """Configurações específicas de cada câmera"""
    
    camera = models.OneToOneField(Camera, on_delete=models.CASCADE, related_name='settings')
    motion_sensitivity = models.FloatField(default=0.3, verbose_name='Sensibilidade de Movimento')
    recording_quality = models.CharField(max_length=20, default='medium', verbose_name='Qualidade da Gravação')
    frame_rate = models.IntegerField(default=15, verbose_name='Taxa de Frames')
    resolution_width = models.IntegerField(default=1920, verbose_name='Largura da Resolução')
    resolution_height = models.IntegerField(default=1080, verbose_name='Altura da Resolução')
    recording_duration = models.IntegerField(default=30, verbose_name='Duração da Gravação (segundos)')
    motion_timeout = models.IntegerField(default=4, verbose_name='Timeout de Movimento (segundos)')
    motion_start_delay = models.IntegerField(default=10, verbose_name='Delay de Início (segundos)')
    
    class Meta:
        verbose_name = 'Configuração de Câmera'
        verbose_name_plural = 'Configurações de Câmeras'
    
    def __str__(self):
        return f"Configurações de {self.camera.name}"


class CameraDiscovery(models.Model):
    """Modelo para armazenar câmeras descobertas via ONVIF"""
    
    DISCOVERY_STATUS = [
        ('discovered', 'Descoberta'),
        ('added', 'Adicionada'),
        ('ignored', 'Ignorada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = models.GenericIPAddressField(verbose_name='Endereço IP')
    port = models.IntegerField(default=80, verbose_name='Porta')
    manufacturer = models.CharField(max_length=100, blank=True, verbose_name='Fabricante')
    model = models.CharField(max_length=100, blank=True, verbose_name='Modelo')
    serial_number = models.CharField(max_length=100, blank=True, verbose_name='Número de Série')
    firmware_version = models.CharField(max_length=50, blank=True, verbose_name='Versão do Firmware')
    onvif_url = models.URLField(blank=True, verbose_name='URL ONVIF')
    rtsp_url = models.URLField(blank=True, verbose_name='URL RTSP')
    status = models.CharField(max_length=20, choices=DISCOVERY_STATUS, default='discovered', verbose_name='Status')
    discovered_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Descoberta')
    added_at = models.DateTimeField(null=True, blank=True, verbose_name='Data de Adição')
    
    class Meta:
        verbose_name = 'Câmera Descoberta'
        verbose_name_plural = 'Câmeras Descobertas'
        ordering = ['-discovered_at']
    
    def __str__(self):
        return f"{self.manufacturer} {self.model} ({self.ip_address})" 