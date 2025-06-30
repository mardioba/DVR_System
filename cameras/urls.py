from django.urls import path
from . import views

app_name = 'cameras'

urlpatterns = [
    # Dashboard e listagem
    path('dashboard/', views.dashboard, name='dashboard'),
    path('list/', views.camera_list, name='camera_list'),
    
    # CRUD de câmeras
    path('create/', views.camera_create, name='camera_create'),
    path('<uuid:camera_id>/', views.camera_detail, name='camera_detail'),
    path('<uuid:camera_id>/edit/', views.camera_edit, name='camera_edit'),
    path('<uuid:camera_id>/delete/', views.camera_delete, name='camera_delete'),
    path('<uuid:camera_id>/settings/', views.camera_settings, name='camera_settings'),
    
    # Visualização ao vivo
    path('<uuid:camera_id>/live/', views.camera_live_view, name='camera_live_view'),
    path('<uuid:camera_id>/stream/', views.camera_stream, name='camera_stream'),
    path('<uuid:camera_id>/snapshot/', views.camera_snapshot, name='camera_snapshot'),
    
    # Descoberta de câmeras
    path('discovery/', views.camera_discovery, name='camera_discovery'),
    path('discovery/<uuid:discovery_id>/add/', views.add_discovered_camera, name='add_discovered_camera'),
    path('discovery/<uuid:discovery_id>/ignore/', views.ignore_discovered_camera, name='ignore_discovered_camera'),
    
    # Gravação manual
    path('<uuid:camera_id>/manual-recording/', views.camera_manual_recording, name='camera_manual_recording'),
    
    # API endpoints
    path('api/cameras/', views.api_camera_list, name='api_camera_list'),
    path('api/cameras/<uuid:camera_id>/status/', views.api_camera_status, name='api_camera_status'),
    path('api/cameras/<uuid:camera_id>/motion/', views.api_motion_detected, name='api_motion_detected'),
    
    # Detecção de movimento
    path('motion-detection/start/', views.start_motion_detection_view, name='start_motion_detection'),
    path('motion-detection/stop/', views.stop_motion_detection_view, name='stop_motion_detection'),
    path('motion-detection/status/', views.motion_detection_status_view, name='motion_detection_status'),
] 