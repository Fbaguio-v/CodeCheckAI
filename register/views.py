from django.shortcuts import render, redirect
from django.views.generic import View
from .forms import RegisterForm, CustomLoginForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login

# Create your views here.
class RegisterView(View):
    def get(self, request):
        form = RegisterForm()
        return render(request, 'register/register.html', {"form" : form})
    
    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, "Account created successfully. Please check your email for confirmation.")
                return redirect('login')
            except Exception as e:
                messages.error(request, f"Error creating user account: {e}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")

        return render(request, 'register/register.html', {'form': form})
    
class LoginView(View):
    def get(self, request):
        form = CustomLoginForm()
        return render(request, 'registration/login.html', {"form" : form})
    
    def post(self, request):
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            try:
                user = User.objects.get(email = email)
                user = authenticate(request, username = user.username, password = password)

                if user is not None:
                    login(request, user)
                    messages.success(request, "Login successfully.")
                    return redirect("a_classroom:index")
                else:
                    messages.error(request, "Invalid email or password.")
            except User.DoesNotExist:
                messages.error(request, "No account found with this email.")
        return render(request, 'registration/login.html', {"form" : form})