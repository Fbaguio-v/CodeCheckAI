from django.urls import path
from . import views

app_name = "c_activities"
urlpatterns = [
	path("", views.CreateActivityView.as_view(), name="create-activity"),
	path("g/", views.StudentGradeView.as_view(), name="grade-a-student"),
	path("e/<int:submission_id>/", views.EditGradeView.as_view(), name="edit-grade"),
	path("edit-activity/<str:activity_id>/", views.EditActivityView.as_view(), name="edit-activity"),
	path("edit-insight/<int:submission_id>/", views.EditInsightView.as_view(), name="edit-insight"),
	path("return/<str:submission_id>/", views.return_submission, name="return-grade"),
	path("delete-activity/<str:activity_id>/", views.delete_activity, name="delete-activity")
]