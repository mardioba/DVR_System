from django.urls import path
from . import views

app_name = 'recordings'

urlpatterns = [
    # Listagem e visualização
    path('', views.recording_list, name='recording_list'),
    path('<uuid:recording_id>/', views.recording_detail, name='recording_detail'),
    path('<uuid:recording_id>/play/', views.recording_play, name='recording_play'),
    path('<uuid:recording_id>/play/test/', views.recording_play_test, name='recording_play_test'),
    path('<uuid:recording_id>/stream/', views.recording_stream, name='recording_stream'),
    path('<uuid:recording_id>/static/', views.recording_static, name='recording_static'),
    path('<uuid:recording_id>/download/', views.recording_download, name='recording_download'),
    path('<uuid:recording_id>/download/converted/', views.recording_download_converted, name='recording_download_converted'),
    
    # Conversão
    path('<uuid:recording_id>/convert/', views.recording_convert, name='recording_convert'),
    path('batch-convert/', views.recording_batch_convert, name='recording_batch_convert'),
    path('<uuid:recording_id>/conversion-status/', views.recording_conversion_status, name='recording_conversion_status'),
    path('conversion-queue/', views.recording_conversion_queue, name='recording_conversion_queue'),
    path('cleanup-converted/', views.recording_cleanup_converted, name='recording_cleanup_converted'),
    
    # Exclusão
    path('<uuid:recording_id>/delete/', views.recording_delete, name='recording_delete'),
    path('bulk-delete/', views.recording_bulk_delete, name='recording_bulk_delete'),
    
    # Configurações e estatísticas
    path('settings/', views.recording_settings, name='recording_settings'),
    path('statistics/', views.recording_statistics, name='recording_statistics'),
    path('motion-events/', views.motion_events, name='motion_events'),
    
    # API endpoints
    path('api/list/', views.api_recording_list, name='api_recording_list'),
    path('api/<uuid:recording_id>/delete/', views.api_recording_delete, name='api_recording_delete'),
] 