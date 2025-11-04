from django.shortcuts import render, redirect
from django.views.generic import View
from .forms import RegisterForm, CustomLoginForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django_user_agents.utils import get_user_agent

# Create your views here.
class RegisterView(View):
    def get(self, request):
        form = RegisterForm()
        user_agent = get_user_agent(request)
        if user_agent.is_mobile or user_agent.is_tablet:
            messages.warning(request, "This platform is optimized for desktop and laptop computers. Please use a PC or laptop for the best coding experience.")
        return render(request, 'register/register.html', {"form": form})
    
    def post(self, request):
        form = RegisterForm(request.POST)
        
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, "Account created successfully. Please check your email for acknowledgement.")
                return redirect('register:login')
            except Exception as e:
                messages.error(request, f"Error creating user account: {e}")
        else:
            # Show only the first form error message (one at a time)
            first_error = next(iter(form.errors.items()), None)
            if first_error:
                field, errors = first_error
                error = errors[0] if errors else "Invalid input."
                if field == 'agree_terms':
                    messages.error(request, error)
                else:
                    field_name = field.replace('_', ' ').capitalize()
                    messages.error(request, f"{field_name}: {error}")
#

        return render(request, 'register/register.html', {'form': form})
    
class LoginView(View):
    def get(self, request):
        form = CustomLoginForm()
        user_agent = get_user_agent(request)
        if user_agent.is_mobile or user_agent.is_tablet:
            messages.warning(request, "This platform is optimized for desktop and laptop computers. Please use a PC or laptop for the best coding experience.")
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