from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User


def login_view(request):
    if request.user.is_authenticated:
        return redirect('cameras:dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bem-vindo, {user.username}!')
            return redirect('cameras:dashboard')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form, 'title': 'Login - Sistema DVR'})


def logout_view(request):
    logout(request)
    messages.info(request, 'Você foi desconectado com sucesso.')
    return redirect('users:login')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('cameras:dashboard')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Conta criada com sucesso!')
            return redirect('cameras:dashboard')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = UserCreationForm()
    return render(request, 'users/register.html', {'form': form, 'title': 'Registro - Sistema DVR'})


@login_required
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        messages.success(request, 'Perfil atualizado com sucesso!')
        return redirect('users:profile')
    return render(request, 'users/profile.html', {'user': request.user, 'title': 'Meu Perfil'})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        if not request.user.check_password(current_password):
            messages.error(request, 'Senha atual incorreta.')
            return redirect('users:change_password')
        if new_password1 != new_password2:
            messages.error(request, 'As novas senhas não coincidem.')
            return redirect('users:change_password')
        if len(new_password1) < 8:
            messages.error(request, 'A nova senha deve ter pelo menos 8 caracteres.')
            return redirect('users:change_password')
        request.user.set_password(new_password1)
        request.user.save()
        user = authenticate(username=request.user.username, password=new_password1)
        login(request, user)
        messages.success(request, 'Senha alterada com sucesso!')
        return redirect('users:profile')
    return render(request, 'users/change_password.html', {'title': 'Alterar Senha'}) 