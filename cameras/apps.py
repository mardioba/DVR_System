from django.apps import AppConfig


class CamerasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cameras'

    def ready(self):
        import sys
        if 'runserver' in sys.argv:
            from cameras.motion_detection import motion_detector
            import threading
            def start_motion():
                print("🔄 Iniciando detecção de movimento automática...")
                motion_detector.start_detection_for_all_cameras()
            threading.Thread(target=start_motion, daemon=True).start() 