from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, Http404, StreamingHttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.conf import settings
import os
from datetime import datetime, timedelta
import mimetypes
import re

from .models import Recording, RecordingSettings, MotionEvent
from .forms import RecordingSettingsForm
from .utils import convert_recording, batch_convert_recordings, get_video_info, cleanup_converted_files
from cameras.models import Camera


@login_required
def recording_list(request):
    """Lista todas as gravações"""
    recordings = Recording.objects.filter(is_deleted=False).order_by('-start_time')
    
    # Filtros
    camera_id = request.GET.get('camera')
    recording_type = request.GET.get('type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if camera_id:
        recordings = recordings.filter(camera_id=camera_id)
    
    if recording_type:
        recordings = recordings.filter(recording_type=recording_type)
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
            recordings = recordings.filter(start_time__date__gte=date_from.date())
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d')
            recordings = recordings.filter(start_time__date__lte=date_to.date())
        except ValueError:
            pass
    
    # Paginação
    paginator = Paginator(recordings, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas
    total_recordings = recordings.count()
    total_size = recordings.aggregate(total_size=Sum('file_size'))['total_size'] or 0
    total_size_gb = round(total_size / (1024**3), 2)
    
    context = {
        'page_obj': page_obj,
        'total_recordings': total_recordings,
        'total_size_gb': total_size_gb,
        'cameras': Camera.objects.filter(is_active=True),
    }
    
    return render(request, 'recordings/recording_list.html', context)


@login_required
def recording_detail(request, recording_id):
    """Detalhes de uma gravação específica"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    context = {
        'recording': recording,
    }
    
    return render(request, 'recordings/recording_detail.html', context)


@login_required
def recording_play(request, recording_id):
    """Reproduzir uma gravação"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    if not os.path.exists(recording.file_path):
        messages.error(request, 'Arquivo de gravação não encontrado.')
        return redirect('recordings:recording_list')
    
    context = {
        'recording': recording,
    }
    
    return render(request, 'recordings/recording_play.html', context)


@login_required
def recording_download(request, recording_id):
    """Download de uma gravação"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    # Priorizar arquivo convertido se disponível
    if recording.converted_file_exists:
        file_path = recording.converted_file_path
        file_name = recording.converted_file_name
    elif recording.file_exists:
        file_path = recording.file_path
        file_name = recording.file_name
    else:
        raise Http404("Arquivo não encontrado")
    
    # Determinar tipo MIME
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'
    
    # Criar resposta de arquivo
    response = FileResponse(
        open(file_path, 'rb'),
        content_type=content_type
    )
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    
    return response


@login_required
def recording_download_converted(request, recording_id):
    """Download específico do arquivo convertido"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    if not recording.converted_file_exists:
        raise Http404("Arquivo convertido não encontrado")
    
    # Determinar tipo MIME
    content_type, _ = mimetypes.guess_type(recording.converted_file_path)
    if content_type is None:
        content_type = 'video/mp4'
    
    # Criar resposta de arquivo
    response = FileResponse(
        open(recording.converted_file_path, 'rb'),
        content_type=content_type
    )
    response['Content-Disposition'] = f'attachment; filename="{recording.converted_file_name}"'
    
    return response


@login_required
def recording_stream(request, recording_id):
    """Stream de uma gravação para o player de vídeo"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    # SEMPRE priorizar arquivo convertido para streaming (H.264 é compatível com navegadores)
    if recording.converted_file_exists:
        file_path = recording.converted_file_path
        content_type = 'video/mp4'
        print(f"🎬 Usando arquivo convertido H.264 para streaming: {recording.converted_file_name}")
    elif recording.file_exists:
        # Se não há arquivo convertido, verificar se o original é compatível
        video_info = get_video_info(recording.file_path)
        if video_info and video_info['video_codec'] in ['h264', 'h265', 'avc1']:
            file_path = recording.file_path
            content_type = 'video/mp4'
            print(f"🎬 Usando arquivo original H.264 para streaming: {recording.file_name}")
        else:
            # Arquivo original não é compatível com navegadores
            codec = video_info.get('video_codec', 'desconhecido') if video_info else 'desconhecido'
            print(f"❌ Arquivo original usa codec {codec} - não compatível com navegadores")
            raise Http404("Vídeo não compatível com navegadores web. Use o arquivo convertido H.264.")
    else:
        raise Http404("Arquivo não encontrado")
    
    # Verificar se é uma requisição de range (necessário para streaming)
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    
    if range_match:
        # Requisição de range - implementar streaming parcial
        start = int(range_match.group(1))
        end = range_match.group(2)
        
        if end:
            end = int(end)
        else:
            end = os.path.getsize(file_path) - 1
        
        length = end - start + 1
        
        try:
            with open(file_path, 'rb') as f:
                f.seek(start)
                data = f.read(length)
            
            response = StreamingHttpResponse([data], status=206)
            response['Content-Range'] = f'bytes {start}-{end}/{os.path.getsize(file_path)}'
            response['Content-Length'] = str(length)
            response['Accept-Ranges'] = 'bytes'
            response['Content-Type'] = content_type
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, HEAD'
            response['Access-Control-Allow-Headers'] = 'Range'
            
            return response
        except Exception as e:
            print(f"❌ Erro no streaming parcial: {e}")
            # Fallback para arquivo completo
            pass
    else:
        # Requisição normal - servir arquivo completo
        try:
            response = FileResponse(
                open(file_path, 'rb'),
                content_type=content_type
            )
            response['Content-Disposition'] = 'inline'
            response['Accept-Ranges'] = 'bytes'
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, HEAD'
            response['Access-Control-Allow-Headers'] = 'Range'
            
            return response
        except Exception as e:
            print(f"❌ Erro ao servir arquivo: {e}")
            raise Http404("Erro ao acessar arquivo")


@login_required
def recording_static(request, recording_id):
    """Serve o vídeo como arquivo estático (alternativa para compatibilidade)"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    if not os.path.exists(recording.file_path):
        raise Http404("Arquivo não encontrado")
    
    # Servir como arquivo estático simples
    response = FileResponse(
        open(recording.file_path, 'rb'),
        content_type='video/mp4'
    )
    response['Content-Disposition'] = 'inline'
    
    return response


@login_required
def recording_delete(request, recording_id):
    """Excluir uma gravação"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    if request.method == 'POST':
        # Excluir arquivo físico
        if recording.delete_file():
            recording.is_deleted = True
            recording.save()
            messages.success(request, 'Gravação excluída com sucesso!')
            return redirect('recordings:recording_list')
        else:
            messages.error(request, 'Erro ao excluir arquivo da gravação.')
            return redirect('recordings:recording_list')
    
    messages.error(request, 'Gravação não encontrada.')
    return redirect('recordings:recording_list')


@login_required
def recording_bulk_delete(request):
    """Exclusão em lote de gravações"""
    if request.method == 'POST':
        recording_ids = request.POST.getlist('recordings')
        days_old = request.POST.get('days_old')
        
        if recording_ids:
            # Excluir gravações específicas
            recordings = Recording.objects.filter(id__in=recording_ids, is_deleted=False)
        elif days_old:
            # Excluir gravações mais antigas que X dias
            cutoff_date = timezone.now() - timedelta(days=int(days_old))
            recordings = Recording.objects.filter(
                start_time__lt=cutoff_date,
                is_deleted=False
            )
        else:
            messages.error(request, 'Nenhuma gravação selecionada para exclusão.')
            return redirect('recordings:recording_list')
        
        deleted_count = 0
        for recording in recordings:
            if recording.delete_file():
                recording.is_deleted = True
                recording.save()
                deleted_count += 1
        
        messages.success(request, f'{deleted_count} gravações excluídas com sucesso!')
        return redirect('recordings:recording_list')
    
    return redirect('recordings:recording_list')


@login_required
def recording_settings(request):
    """Configurações de gravação"""
    settings_obj = RecordingSettings.get_settings()
    
    if request.method == 'POST':
        form = RecordingSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configurações de gravação atualizadas!')
            return redirect('recordings:recording_settings')
    else:
        form = RecordingSettingsForm(instance=settings_obj)
    
    # Estatísticas de armazenamento
    total_recordings = Recording.objects.filter(is_deleted=False).count()
    total_size = Recording.objects.filter(is_deleted=False).aggregate(
        total_size=Sum('file_size')
    )['total_size'] or 0
    total_size_gb = round(total_size / (1024**3), 2)
    
    context = {
        'form': form,
        'total_recordings': total_recordings,
        'total_size_gb': total_size_gb,
        'storage_limit_gb': settings_obj.storage_limit_gb,
    }
    
    return render(request, 'recordings/recording_settings.html', context)


@login_required
def motion_events(request):
    """Lista eventos de movimento"""
    events = MotionEvent.objects.all().order_by('-start_time')
    
    # Filtros
    camera_id = request.GET.get('camera')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if camera_id:
        events = events.filter(camera_id=camera_id)
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
            events = events.filter(start_time__date__gte=date_from.date())
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d')
            events = events.filter(start_time__date__lte=date_to.date())
        except ValueError:
            pass
    
    # Paginação
    paginator = Paginator(events, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'cameras': Camera.objects.filter(is_active=True),
    }
    
    return render(request, 'recordings/motion_events.html', context)


@login_required
def recording_statistics(request):
    """Estatísticas de gravação"""
    # Estatísticas por câmera
    camera_stats = []
    cameras = Camera.objects.filter(is_active=True)
    
    for camera in cameras:
        recordings = Recording.objects.filter(camera=camera, is_deleted=False)
        total_recordings = recordings.count()
        total_size = recordings.aggregate(total_size=Sum('file_size'))['total_size'] or 0
        total_size_gb = round(total_size / (1024**3), 2)
        
        # Gravações dos últimos 7 dias
        week_ago = timezone.now() - timedelta(days=7)
        recent_recordings = recordings.filter(start_time__gte=week_ago).count()
        
        camera_stats.append({
            'camera': camera,
            'total_recordings': total_recordings,
            'total_size_gb': total_size_gb,
            'recent_recordings': recent_recordings,
        })
    
    # Estatísticas por tipo de gravação
    type_stats = Recording.objects.filter(is_deleted=False).values('recording_type').annotate(
        count=models.Count('id'),
        total_size=Sum('file_size')
    )
    
    # Estatísticas por data (últimos 30 dias)
    date_stats = []
    for i in range(30):
        date = timezone.now().date() - timedelta(days=i)
        count = Recording.objects.filter(
            start_time__date=date,
            is_deleted=False
        ).count()
        
        date_stats.append({
            'date': date,
            'count': count,
        })
    
    date_stats.reverse()
    
    context = {
        'camera_stats': camera_stats,
        'type_stats': type_stats,
        'date_stats': date_stats,
    }
    
    return render(request, 'recordings/recording_statistics.html', context)


# API Views
@login_required
def api_recording_list(request):
    """API para listar gravações"""
    recordings = Recording.objects.filter(is_deleted=False).order_by('-start_time')
    
    # Filtros
    camera_id = request.GET.get('camera')
    if camera_id:
        recordings = recordings.filter(camera_id=camera_id)
    
    data = []
    for recording in recordings[:50]:  # Limitar a 50 resultados
        data.append({
            'id': str(recording.id),
            'camera_name': recording.camera.name,
            'file_name': recording.file_name,
            'duration': recording.duration,
            'file_size_mb': recording.get_file_size_mb(),
            'recording_type': recording.recording_type,
            'start_time': recording.start_time.isoformat(),
            'motion_detected': recording.motion_detected,
        })
    
    return JsonResponse({'recordings': data})


@login_required
def api_recording_delete(request, recording_id):
    """API para excluir gravação"""
    try:
        recording = Recording.objects.get(id=recording_id, is_deleted=False)
        
        if recording.delete_file():
            recording.is_deleted = True
            recording.save()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'error': 'Erro ao excluir arquivo'}, status=500)
            
    except Recording.DoesNotExist:
        return JsonResponse({'error': 'Gravação não encontrada'}, status=404)


# Views de Conversão
@login_required
def recording_convert(request, recording_id):
    """Converte uma gravação para H.264"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    if request.method == 'POST':
        quality = request.POST.get('quality', 'medium')
        
        # Verificar se já foi convertido
        if recording.conversion_status == 'completed' and recording.converted_file_exists:
            messages.info(request, 'Esta gravação já foi convertida.')
            return redirect('recordings:recording_detail', recording_id=recording_id)
        
        # Verificar se está sendo convertida
        if recording.conversion_status == 'converting':
            messages.warning(request, 'Esta gravação está sendo convertida. Aguarde...')
            return redirect('recordings:recording_detail', recording_id=recording_id)
        
        # Iniciar conversão
        result = convert_recording(recording_id, quality)
        
        if result['success']:
            messages.success(request, f'Conversão iniciada com sucesso! Arquivo: {recording.converted_file_name}')
        else:
            messages.error(request, f'Erro na conversão: {result["error"]}')
        
        return redirect('recordings:recording_detail', recording_id=recording_id)
    
    # GET - mostrar formulário de conversão
    context = {
        'recording': recording,
        'video_info': get_video_info(recording.file_path) if recording.file_exists else None,
    }
    
    return render(request, 'recordings/recording_convert.html', context)


@login_required
def recording_batch_convert(request):
    """Conversão em lote de gravações"""
    if request.method == 'POST':
        recording_ids = request.POST.getlist('recordings')
        quality = request.POST.get('quality', 'medium')
        
        if not recording_ids:
            messages.error(request, 'Nenhuma gravação selecionada para conversão.')
            return redirect('recordings:recording_list')
        
        # Filtrar gravações que podem ser convertidas
        recordings = Recording.objects.filter(
            id__in=recording_ids,
            is_deleted=False,
            conversion_status__in=['pending', 'failed']
        )
        
        if not recordings:
            messages.warning(request, 'Nenhuma gravação válida encontrada para conversão.')
            return redirect('recordings:recording_list')
        
        # Iniciar conversão em lote
        result = batch_convert_recordings([str(r.id) for r in recordings], quality)
        
        if result['success'] > 0:
            messages.success(request, f'{result["success"]} gravações convertidas com sucesso!')
        
        if result['failed'] > 0:
            messages.warning(request, f'{result["failed"]} gravações falharam na conversão.')
        
        return redirect('recordings:recording_list')
    
    # GET - mostrar formulário de conversão em lote
    recordings = Recording.objects.filter(
        is_deleted=False,
        conversion_status__in=['pending', 'failed']
    ).order_by('-start_time')
    
    context = {
        'recordings': recordings,
    }
    
    return render(request, 'recordings/recording_batch_convert.html', context)


@login_required
def recording_conversion_status(request, recording_id):
    """API para verificar status da conversão"""
    try:
        recording = Recording.objects.get(id=recording_id, is_deleted=False)
        
        return JsonResponse({
            'status': recording.conversion_status,
            'error': recording.conversion_error,
            'converted_file_exists': recording.converted_file_exists,
            'converted_file_name': recording.converted_file_name,
        })
        
    except Recording.DoesNotExist:
        return JsonResponse({'error': 'Gravação não encontrada'}, status=404)


@login_required
def recording_cleanup_converted(request):
    """Limpa arquivos convertidos órfãos"""
    if request.method == 'POST':
        cleaned_count = cleanup_converted_files()
        
        if cleaned_count > 0:
            messages.success(request, f'{cleaned_count} arquivos órfãos removidos.')
        else:
            messages.info(request, 'Nenhum arquivo órfão encontrado.')
        
        return redirect('recordings:recording_settings')
    
    return redirect('recordings:recording_settings')


@login_required
def recording_conversion_queue(request):
    """Mostra fila de conversão"""
    # Gravações pendentes de conversão
    pending_recordings = Recording.objects.filter(
        conversion_status='pending',
        is_deleted=False
    ).order_by('start_time')
    
    # Gravações sendo convertidas
    converting_recordings = Recording.objects.filter(
        conversion_status='converting',
        is_deleted=False
    ).order_by('start_time')
    
    # Gravações com erro na conversão
    failed_recordings = Recording.objects.filter(
        conversion_status='failed',
        is_deleted=False
    ).order_by('-start_time')
    
    # Gravações convertidas recentemente
    recent_converted = Recording.objects.filter(
        conversion_status='completed',
        is_deleted=False
    ).order_by('-start_time')[:10]
    
    context = {
        'pending_recordings': pending_recordings,
        'converting_recordings': converting_recordings,
        'failed_recordings': failed_recordings,
        'recent_converted': recent_converted,
    }
    
    return render(request, 'recordings/recording_conversion_queue.html', context)


@login_required
def recording_play_test(request, recording_id):
    """Página de teste do player de vídeo"""
    recording = get_object_or_404(Recording, id=recording_id, is_deleted=False)
    
    context = {
        'recording': recording,
    }
    
    return render(request, 'recordings/recording_play_test.html', context) 