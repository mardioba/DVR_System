from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.utils import timezone
from datetime import timedelta


def setup_periodic_tasks():
    """Configura tarefas periódicas do sistema"""
    
    # Tarefa para limpeza automática de gravações antigas
    schedule_cleanup, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.DAYS,
    )
    
    PeriodicTask.objects.get_or_create(
        name='Limpeza automática de gravações',
        task='recordings.tasks.cleanup_old_recordings',
        interval=schedule_cleanup,
        enabled=True,
        defaults={
            'description': 'Remove gravações antigas baseado nas configurações de retenção'
        }
    )
    
    # Tarefa para verificação de limite de armazenamento
    schedule_storage, created = IntervalSchedule.objects.get_or_create(
        every=6,
        period=IntervalSchedule.HOURS,
    )
    
    PeriodicTask.objects.get_or_create(
        name='Verificação de limite de armazenamento',
        task='recordings.tasks.check_storage_limit',
        interval=schedule_storage,
        enabled=True,
        defaults={
            'description': 'Verifica e gerencia limite de armazenamento'
        }
    )
    
    # Tarefa para atualização de status das câmeras
    schedule_status, created = IntervalSchedule.objects.get_or_create(
        every=5,
        period=IntervalSchedule.MINUTES,
    )
    
    PeriodicTask.objects.get_or_create(
        name='Atualização de status das câmeras',
        task='cameras.tasks.update_all_cameras_status',
        interval=schedule_status,
        enabled=True,
        defaults={
            'description': 'Atualiza status de conectividade das câmeras'
        }
    )
    
    # Tarefa para limpeza de descobertas antigas
    schedule_discovery, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.HOURS,
    )
    
    PeriodicTask.objects.get_or_create(
        name='Limpeza de descobertas antigas',
        task='cameras.tasks.cleanup_old_discoveries',
        interval=schedule_discovery,
        enabled=True,
        defaults={
            'description': 'Remove descobertas de câmeras antigas'
        }
    )
    
    print("✅ Tarefas periódicas configuradas com sucesso!")


def disable_all_tasks():
    """Desabilita todas as tarefas periódicas"""
    PeriodicTask.objects.all().update(enabled=False)
    print("✅ Todas as tarefas periódicas foram desabilitadas!")


def enable_all_tasks():
    """Habilita todas as tarefas periódicas"""
    PeriodicTask.objects.all().update(enabled=True)
    print("✅ Todas as tarefas periódicas foram habilitadas!")


def list_tasks():
    """Lista todas as tarefas periódicas"""
    tasks = PeriodicTask.objects.all()
    print("📋 Tarefas Periódicas:")
    print("=" * 50)
    
    for task in tasks:
        status = "✅ Habilitada" if task.enabled else "❌ Desabilitada"
        print(f"• {task.name} - {status}")
        print(f"  Descrição: {task.description}")
        print(f"  Intervalo: {task.interval}")
        print(f"  Próxima execução: {task.next_run_at}")
        print()


if __name__ == "__main__":
    import os
    import django
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dvr_system.settings')
    django.setup()
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "setup":
            setup_periodic_tasks()
        elif command == "disable":
            disable_all_tasks()
        elif command == "enable":
            enable_all_tasks()
        elif command == "list":
            list_tasks()
        else:
            print("Comandos disponíveis:")
            print("  setup   - Configura tarefas periódicas")
            print("  disable - Desabilita todas as tarefas")
            print("  enable  - Habilita todas as tarefas")
            print("  list    - Lista todas as tarefas")
    else:
        setup_periodic_tasks() 