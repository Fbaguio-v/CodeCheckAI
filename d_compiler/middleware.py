from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.urls import resolve, reverse
from b_enrollment.models import UserProfile

class RestrictPlaygroundViewMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        resolver_match = resolve(request.path_info)

        if resolver_match.app_name == "d_compiler" and resolver_match.url_name == "index":
            user = request.user

            if user.is_authenticated:
                try:
                    profile = user.userprofile
                    if profile.role in ["Instructor", "Admin"]:
                        return redirect(reverse("a_classroom:index"))
                except UserProfile.DoesNotExist:
                    return redirect(reverse("register:register"))

        return None
