from django.urls import path
from . import views

app_name = "d_compiler"
urlpatterns = [
    path("", views.CompilerView.as_view(), name="index"),
]