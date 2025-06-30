from django.contrib import admin
from .models import Recording, RecordingSettings, MotionEvent


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ['camera', 'file_name', 'recording_type', 'duration', 'file_size', 'start_time', 'motion_detected', 'is_deleted']
    list_filter = ['recording_type', 'motion_detected', 'start_time', 'is_deleted']
    search_fields = ['camera__name', 'file_name']
    readonly_fields = ['id', 'created_at']
    list_editable = ['is_deleted']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('camera', 'file_name', 'recording_type')
        }),
        ('Arquivo', {
            'fields': ('file_path', 'file_size', 'duration')
        }),
        ('Detecção de Movimento', {
            'fields': ('motion_detected',)
        }),
        ('Timestamps', {
            'fields': ('start_time', 'end_time', 'created_at')
        }),
        ('Sistema', {
            'fields': ('id', 'is_deleted'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['delete_recordings', 'mark_as_deleted']
    
    def delete_recordings(self, request, queryset):
        for recording in queryset:
            recording.delete_file()
        queryset.update(is_deleted=True)
    delete_recordings.short_description = "Excluir gravações permanentemente"
    
    def mark_as_deleted(self, request, queryset):
        queryset.update(is_deleted=True)
    mark_as_deleted.short_description = "Marcar como excluídas"


@admin.register(RecordingSettings)
class RecordingSettingsAdmin(admin.ModelAdmin):
    list_display = ['max_recording_days', 'auto_delete_enabled', 'storage_limit_gb', 'compression_enabled']
    
    fieldsets = (
        ('Retenção', {
            'fields': ('max_recording_days', 'auto_delete_enabled')
        }),
        ('Armazenamento', {
            'fields': ('storage_limit_gb', 'compression_enabled')
        }),
        ('Backup', {
            'fields': ('backup_enabled', 'backup_path')
        }),
    )


@admin.register(MotionEvent)
class MotionEventAdmin(admin.ModelAdmin):
    list_display = ['camera', 'start_time', 'duration', 'confidence', 'area_affected']
    list_filter = ['start_time', 'camera']
    search_fields = ['camera__name']
    readonly_fields = ['id', 'start_time', 'end_time']
    
    fieldsets = (
        ('Evento', {
            'fields': ('camera', 'recording', 'start_time', 'end_time', 'duration')
        }),
        ('Detecção', {
            'fields': ('confidence', 'area_affected')
        }),
    ) 