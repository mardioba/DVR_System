from django.apps import AppConfig


class RecordingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recordings'
    verbose_name = 'Gravações'
    
    def ready(self):
        # Importar signals quando o app for carregado
        import recordings.signals 