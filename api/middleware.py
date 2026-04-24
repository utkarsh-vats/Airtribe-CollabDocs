import time

class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration_ms = (time.time() - start_time) * 1000
        print(
            f"{request.method} \t{request.path} \t- \t{response.status_code} \t- \t{duration_ms:.2f}ms"
        )
        return response