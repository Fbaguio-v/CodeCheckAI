from django.urls import path
from . import views

app_name = "d_compiler"
urlpatterns = [
    path("", views.CompilerView.as_view(), name="index"),
    path("turn_in/", views.TurnInView.as_view(), name="turn_in"),
    path("save_draft/", views.SaveDraftView.as_view(), name="save_draft"),
    path("unsubmit/", views.UnsubmitView.as_view(), name="unsubmit"),
]