from django.shortcuts import redirect
from django.urls import resolve, reverse
from b_enrollment.models import UserProfile

class InstructorOnlyMiddleware:
    restricted_urls = [
        "create-activity",
        "grade-a-student",
        "edit-grade",
        "edit-activity",
        "edit-insight",
        "return-grade",
        "delete-activity"
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        resolver_match = resolve(request.path_info)

        if resolver_match.url_name in self.restricted_urls:
            user = request.user

            if not user.is_authenticated:
                return redirect(reverse("register:login"))

            try:
                profile = user.userprofile
                if profile.role != "Instructor":
                    return redirect(reverse("a_classroom:index"))
            except UserProfile.DoesNotExist:
                return redirect(reverse("register:login"))

        return None