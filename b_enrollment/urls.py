from django.urls import path
from . import views

app_name = "b_enrollment"
urlpatterns = [
	path("", views.JoinClassView.as_view(), name="join-a-class"),
	path("p/", views.UploadProfileView.as_view(), name="upload-profile"),
	path("u/", views.UnenrollClassView.as_view(), name="unenroll"),
	]