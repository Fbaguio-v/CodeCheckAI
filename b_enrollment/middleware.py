from django.shortcuts import redirect
from django.urls import resolve, reverse
from b_enrollment.models import UserProfile

class B_EnrollmentMiddleware:
    restricted_urls = [
        "upload-profile",
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
            except UserProfile.DoesNotExist:
                return redirect(reverse("register:login"))

        return None

class StudentOnlyMiddleware:
    restricted_urls = [
        "join-a-class",
        "unenroll",
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
                if profile.role != "Student":
                    return redirect(reverse("a_classroom:index"))
            except UserProfile.DoesNotExist:
                return redirect(reverse("register:login"))

        return None