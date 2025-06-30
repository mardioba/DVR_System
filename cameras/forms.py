from django import forms
from .models import Camera, CameraSettings
import re


class CameraForm(forms.ModelForm):
    """Formulário para criação e edição de câmeras"""
    
    class Meta:
        model = Camera
        fields = [
            'name', 'description', 'ip_address', 'port', 'stream_url',
            'camera_type', 'username', 'password', 'motion_detection_enabled',
            'recording_enabled', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'stream_url': forms.TextInput(attrs={'class': 'form-control'}),  # Mudado de URLInput para TextInput
            'camera_type': forms.Select(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'motion_detection_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recording_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_stream_url(self):
        """Validação da URL do stream"""
        url = self.cleaned_data['stream_url']
        if not url:
            raise forms.ValidationError('URL do stream é obrigatória.')
        
        # Permitir URLs RTSP, HTTP, HTTPS e outras URLs válidas
        url_pattern = re.compile(
            r'^(https?|rtsp)://'  # http://, https:// ou rtsp://
            r'([\w\-]+\.)*[\w\-]+'  # domínio ou IP
            r'(:\d+)?'  # porta opcional
            r'(/.*)?$',  # caminho opcional
            re.IGNORECASE
        )
        
        if not url_pattern.match(url):
            raise forms.ValidationError('Digite uma URL válida (HTTP, HTTPS ou RTSP).')
        
        return url
    
    def clean(self):
        """Validação geral do formulário"""
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        # Se um dos campos de autenticação estiver preenchido, ambos devem estar
        if username and not password:
            raise forms.ValidationError('Se o usuário for informado, a senha também deve ser informada.')
        elif password and not username:
            raise forms.ValidationError('Se a senha for informada, o usuário também deve ser informado.')
        
        return cleaned_data


class CameraSettingsForm(forms.ModelForm):
    """Formulário para configurações de câmera"""
    
    class Meta:
        model = CameraSettings
        fields = [
            'motion_sensitivity', 'recording_quality', 'frame_rate',
            'resolution_width', 'resolution_height', 'recording_duration',
            'motion_timeout', 'motion_start_delay'
        ]
        widgets = {
            'motion_sensitivity': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.1', 'min': '0.1', 'max': '1.0'}
            ),
            'recording_quality': forms.Select(
                choices=[('low', 'Baixa'), ('medium', 'Média'), ('high', 'Alta')],
                attrs={'class': 'form-control'}
            ),
            'frame_rate': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '1', 'max': '30'}
            ),
            'resolution_width': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '320', 'max': '3840'}
            ),
            'resolution_height': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '240', 'max': '2160'}
            ),
            'recording_duration': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '10', 'max': '300'}
            ),
            'motion_timeout': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '1', 'max': '30'}
            ),
            'motion_start_delay': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '1', 'max': '60'}
            ),
        }
    
    def clean_motion_sensitivity(self):
        """Validação da sensibilidade de movimento"""
        sensitivity = self.cleaned_data['motion_sensitivity']
        if sensitivity < 0.1 or sensitivity > 1.0:
            raise forms.ValidationError('A sensibilidade deve estar entre 0.1 e 1.0.')
        return sensitivity
    
    def clean_frame_rate(self):
        """Validação da taxa de frames"""
        frame_rate = self.cleaned_data['frame_rate']
        if frame_rate < 1 or frame_rate > 30:
            raise forms.ValidationError('A taxa de frames deve estar entre 1 e 30.')
        return frame_rate
    
    def clean_recording_duration(self):
        """Validação da duração da gravação"""
        duration = self.cleaned_data['recording_duration']
        if duration < 10 or duration > 300:
            raise forms.ValidationError('A duração da gravação deve estar entre 10 e 300 segundos.')
        return duration 