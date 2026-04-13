from django.utils.cache import add_never_cache_headers


class NoCacheAfterLogoutMiddleware:
    """
    Prevents the browser from serving cached authenticated pages
    after the user logs out.

    Sets Cache-Control: no-cache, no-store, must-revalidate on every
    response for authenticated users, so the browser's Back/Forward
    buttons always re-validate with the server.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            add_never_cache_headers(response)

        return response
