from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from recordings.models import Recording
from recordings.utils import convert_recording, batch_convert_recordings, get_video_info


class Command(BaseCommand):
    help = 'Converte gravações para H.264'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Converter todas as gravações pendentes',
        )
        parser.add_argument(
            '--recording-id',
            type=str,
            help='ID específico da gravação para converter',
        )
        parser.add_argument(
            '--quality',
            type=str,
            choices=['low', 'medium', 'high'],
            default='medium',
            help='Qualidade da conversão (low, medium, high)',
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Tentar converter novamente gravações que falharam',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Listar gravações disponíveis para conversão',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_recordings()
            return

        if options['recording_id']:
            self.convert_specific_recording(options['recording_id'], options['quality'])
        elif options['all']:
            self.convert_all_pending(options['quality'])
        elif options['retry_failed']:
            self.retry_failed_conversions(options['quality'])
        else:
            self.stdout.write(
                self.style.ERROR('Especifique --all, --recording-id ou --retry-failed')
            )

    def list_recordings(self):
        """Lista gravações disponíveis para conversão"""
        self.stdout.write(self.style.SUCCESS('📋 Gravações disponíveis:'))
        self.stdout.write('=' * 80)

        # Gravações pendentes
        pending = Recording.objects.filter(conversion_status='pending', is_deleted=False)
        if pending.exists():
            self.stdout.write(f'\n⏳ Pendentes ({pending.count()}):')
            for recording in pending[:10]:
                self.stdout.write(f'  {recording.id} - {recording.file_name} ({recording.get_file_size_mb()} MB)')

        # Gravações com erro
        failed = Recording.objects.filter(conversion_status='failed', is_deleted=False)
        if failed.exists():
            self.stdout.write(f'\n❌ Com erro ({failed.count()}):')
            for recording in failed[:10]:
                self.stdout.write(f'  {recording.id} - {recording.file_name} ({recording.get_file_size_mb()} MB)')

        # Gravações convertidas
        completed = Recording.objects.filter(conversion_status='completed', is_deleted=False)
        if completed.exists():
            self.stdout.write(f'\n✅ Convertidas ({completed.count()}):')
            for recording in completed[:5]:
                self.stdout.write(f'  {recording.id} - {recording.file_name} -> {recording.converted_file_name}')

        if not any([pending.exists(), failed.exists(), completed.exists()]):
            self.stdout.write(self.style.WARNING('Nenhuma gravação encontrada'))

    def convert_specific_recording(self, recording_id, quality):
        """Converte uma gravação específica"""
        try:
            recording = Recording.objects.get(id=recording_id, is_deleted=False)
        except Recording.DoesNotExist:
            raise CommandError(f'Gravação {recording_id} não encontrada')

        self.stdout.write(f'🔄 Convertendo gravação: {recording.file_name}')
        self.stdout.write(f'📁 Arquivo: {recording.file_path}')
        self.stdout.write(f'📊 Tamanho: {recording.get_file_size_mb()} MB')
        self.stdout.write(f'🔄 Status atual: {recording.conversion_status}')

        # Verificar se já foi convertido
        if recording.conversion_status == 'completed' and recording.converted_file_exists:
            self.stdout.write(self.style.SUCCESS('✅ Gravação já foi convertida'))
            return

        # Verificar se está sendo convertida
        if recording.conversion_status == 'converting':
            self.stdout.write(self.style.WARNING('⚠️ Gravação está sendo convertida'))
            return

        # Obter informações do vídeo
        video_info = get_video_info(recording.file_path)
        if video_info:
            self.stdout.write(f'📹 Codec: {video_info["video_codec"]}')
            self.stdout.write(f'📐 Resolução: {video_info["video_resolution"]}')
            self.stdout.write(f'⏱️ Duração: {video_info["duration"]:.2f}s')

        # Realizar conversão
        result = convert_recording(recording_id, quality)

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Conversão concluída: {recording.converted_file_name}')
            )
            self.stdout.write(f'📊 Tamanho convertido: {recording.get_converted_file_size_mb()} MB')
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro na conversão: {result["error"]}')
            )

    def convert_all_pending(self, quality):
        """Converte todas as gravações pendentes"""
        pending_recordings = Recording.objects.filter(
            conversion_status='pending',
            is_deleted=False
        )

        if not pending_recordings.exists():
            self.stdout.write(self.style.WARNING('Nenhuma gravação pendente encontrada'))
            return

        self.stdout.write(f'🔄 Convertendo {pending_recordings.count()} gravações pendentes...')

        recording_ids = [str(r.id) for r in pending_recordings]
        result = batch_convert_recordings(recording_ids, quality)

        self.stdout.write(
            self.style.SUCCESS(f'✅ Conversão em lote concluída: {result["success"]} sucessos, {result["failed"]} falhas')
        )

        if result['errors']:
            self.stdout.write(self.style.ERROR('❌ Erros encontrados:'))
            for error in result['errors'][:5]:  # Mostrar apenas os primeiros 5 erros
                self.stdout.write(f'  - {error}')

    def retry_failed_conversions(self, quality):
        """Tenta converter novamente gravações que falharam"""
        failed_recordings = Recording.objects.filter(
            conversion_status='failed',
            is_deleted=False
        )

        if not failed_recordings.exists():
            self.stdout.write(self.style.WARNING('Nenhuma gravação com erro encontrada'))
            return

        self.stdout.write(f'🔄 Tentando converter novamente {failed_recordings.count()} gravações...')

        # Resetar status para pending
        failed_recordings.update(conversion_status='pending', conversion_error=None)

        recording_ids = [str(r.id) for r in failed_recordings]
        result = batch_convert_recordings(recording_ids, quality)

        self.stdout.write(
            self.style.SUCCESS(f'✅ Reconversão concluída: {result["success"]} sucessos, {result["failed"]} falhas')
        ) 