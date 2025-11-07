from django.urls import path
from . import views

app_name = "b_enrollment"
urlpatterns = [
	path("", views.JoinClassView.as_view(), name="join-a-class"),
	path("upload-profile/", views.UploadProfileView.as_view(), name="upload-profile"),
	path("unenroll/", views.UnenrollClassView.as_view(), name="unenroll"),
	]