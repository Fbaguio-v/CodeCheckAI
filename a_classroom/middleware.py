from django.shortcuts import redirect
from django.urls import resolve, Resolver404, reverse
from b_enrollment.models import UserProfile


class A_ClassroomMiddleware:
    restricted_urls = [
        "view-activity",
        "setting",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == "/" and request.user.is_authenticated:
            return redirect("a_classroom:index")
            
        if request.path_info == "/" and not request.user.is_authenticated:
            return redirect("d_compiler:index")

        try:
            resolver_match = resolve(request.path_info)
        except Resolver404:
            return self.get_response(request)

        if resolver_match.url_name in self.restricted_urls:
            user = request.user
            if not user.is_authenticated:
                return redirect(reverse("register:login"))

            try:
                profile = user.userprofile
            except UserProfile.DoesNotExist:
                return redirect(reverse("register:login"))

        return self.get_response(request)

class InstructorOnlyMiddleware:
    restricted_urls = [
        "create-subject",
        "prev_or_next",
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

class AdminOnlyMiddleware:
    restricted_urls = [
        "approve",
        "get-users",
        "pending-users",
        "get-subjects",
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
                if profile.role != "Admin":
                    return redirect(reverse("a_classroom:index"))
            except UserProfile.DoesNotExist:
                return redirect(reverse("register:login"))

        return None

class SuperAdminOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            user = request.user

            if not user.is_authenticated:
                return redirect(reverse("register:login"))

            if not user.is_superuser:
                return redirect(reverse("register:login"))

        return self.get_response(request)