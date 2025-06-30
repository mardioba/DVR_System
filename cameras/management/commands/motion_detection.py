from django.core.management.base import BaseCommand
from cameras.motion_detection import start_motion_detection, stop_motion_detection, get_detection_status


class Command(BaseCommand):
    help = 'Controla a detecção de movimento das câmeras'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['start', 'stop', 'status'],
            help='Ação a ser executada: start, stop ou status'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'start':
            result = start_motion_detection()
            self.stdout.write(
                self.style.SUCCESS(f'✅ {result}')
            )
            
        elif action == 'stop':
            result = stop_motion_detection()
            self.stdout.write(
                self.style.WARNING(f'🛑 {result}')
            )
            
        elif action == 'status':
            status = get_detection_status()
            self.stdout.write(
                self.style.SUCCESS(f'📊 Status da Detecção de Movimento:')
            )
            self.stdout.write(f'   • Câmeras ativas: {status["total_active"]}')
            self.stdout.write(f'   • Gravando: {status["recording_cameras"]}')
            
            if status['active_cameras']:
                self.stdout.write(f'   • Câmeras monitorando:')
                for camera in status['active_cameras']:
                    self.stdout.write(f'     - {camera}')
            else:
                self.stdout.write('   • Nenhuma câmera ativa') 