from django.shortcuts import redirect
from django.urls import reverse
from django.utils.cache import patch_cache_control

class NoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

class RedirectAuthenticatedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.restricted_paths = None

    def __call__(self, request):
        if self.restricted_paths is None:
            self.restricted_paths = {reverse('register:login'), reverse('register:register')}
        
        if request.user.is_authenticated and request.path in self.restricted_paths:
            return redirect('a_classroom:index')

        return self.get_response(request)