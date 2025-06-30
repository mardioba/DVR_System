from django.contrib import admin
from .models import Camera, CameraSettings, CameraDiscovery


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['name', 'ip_address', 'camera_type', 'status', 'is_active', 'created_at']
    list_filter = ['status', 'camera_type', 'is_active', 'motion_detection_enabled', 'recording_enabled']
    search_fields = ['name', 'ip_address', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_seen']
    list_editable = ['is_active', 'status']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'description', 'ip_address', 'port')
        }),
        ('Configuração do Stream', {
            'fields': ('stream_url', 'camera_type', 'username', 'password')
        }),
        ('Status e Configurações', {
            'fields': ('status', 'is_active', 'motion_detection_enabled', 'recording_enabled')
        }),
        ('Informações do Sistema', {
            'fields': ('id', 'created_at', 'updated_at', 'last_seen'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CameraSettings)
class CameraSettingsAdmin(admin.ModelAdmin):
    list_display = ['camera', 'motion_sensitivity', 'frame_rate', 'recording_duration']
    list_filter = ['recording_quality']
    search_fields = ['camera__name']
    
    fieldsets = (
        ('Câmera', {
            'fields': ('camera',)
        }),
        ('Detecção de Movimento', {
            'fields': ('motion_sensitivity', 'motion_timeout', 'motion_start_delay')
        }),
        ('Qualidade de Vídeo', {
            'fields': ('recording_quality', 'frame_rate', 'resolution_width', 'resolution_height')
        }),
        ('Gravação', {
            'fields': ('recording_duration',)
        }),
    )


@admin.register(CameraDiscovery)
class CameraDiscoveryAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'manufacturer', 'model', 'status', 'discovered_at']
    list_filter = ['status', 'discovered_at']
    search_fields = ['ip_address', 'manufacturer', 'model', 'serial_number']
    readonly_fields = ['id', 'discovered_at', 'added_at']
    
    fieldsets = (
        ('Informações da Câmera', {
            'fields': ('ip_address', 'port', 'manufacturer', 'model', 'serial_number', 'firmware_version')
        }),
        ('URLs', {
            'fields': ('onvif_url', 'rtsp_url')
        }),
        ('Status', {
            'fields': ('status', 'discovered_at', 'added_at')
        }),
    )
    
    actions = ['mark_as_added', 'mark_as_ignored']
    
    def mark_as_added(self, request, queryset):
        queryset.update(status='added')
    mark_as_added.short_description = "Marcar como adicionadas"
    
    def mark_as_ignored(self, request, queryset):
        queryset.update(status='ignored')
    mark_as_ignored.short_description = "Marcar como ignoradas" 