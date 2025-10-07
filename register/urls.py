from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "register"
urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    
    path('password_reset/', 
        auth_views.PasswordResetView.as_view(
            template_name='forgot_password/password_reset_form.html',
            email_template_name='forgot_password/password_reset_email.html'
        ), 
        name='password_reset'),
    path('password_reset/done/', 

    auth_views.PasswordResetDoneView.as_view(
        template_name='forgot_password/password_reset_done.html'
    ), 
    name='password_reset_done'),

    path('reset/<uidb64>/<token>/', 
        auth_views.PasswordResetConfirmView.as_view(
            template_name='forgot_password/password_reset_confirm.html'
        ), 
        name='password_reset_confirm'),

    path('reset/done/', 
        auth_views.PasswordResetCompleteView.as_view(
            template_name='forgot_password/password_reset_complete.html'
        ), 
        name='password_reset_complete'),
]