from django import forms
from .models import RecordingSettings


class RecordingSettingsForm(forms.ModelForm):
    """Formulário para configurações de gravação"""
    
    class Meta:
        model = RecordingSettings
        fields = [
            'max_recording_days', 'auto_delete_enabled', 'storage_limit_gb',
            'compression_enabled', 'backup_enabled', 'backup_path'
        ]
        widgets = {
            'max_recording_days': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '1', 'max': '365'}
            ),
            'auto_delete_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'storage_limit_gb': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '1', 'max': '10000'}
            ),
            'compression_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'backup_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'backup_path': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def clean_max_recording_days(self):
        """Validação dos dias máximos de retenção"""
        days = self.cleaned_data['max_recording_days']
        if days < 1 or days > 365:
            raise forms.ValidationError('Os dias de retenção devem estar entre 1 e 365.')
        return days
    
    def clean_storage_limit_gb(self):
        """Validação do limite de armazenamento"""
        limit = self.cleaned_data['storage_limit_gb']
        if limit < 1 or limit > 10000:
            raise forms.ValidationError('O limite de armazenamento deve estar entre 1 e 10000 GB.')
        return limit
    
    def clean(self):
        """Validação geral do formulário"""
        cleaned_data = super().clean()
        backup_enabled = cleaned_data.get('backup_enabled')
        backup_path = cleaned_data.get('backup_path')
        
        if backup_enabled and not backup_path:
            raise forms.ValidationError('Se o backup estiver habilitado, o caminho deve ser informado.')
        
        return cleaned_data 