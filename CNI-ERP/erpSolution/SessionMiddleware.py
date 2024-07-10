from django.contrib.sessions.middleware import SessionMiddleware

class SessionMiddleware(SessionMiddleware):
    def process_request(self, request):
        if request.path.startswith("/inbox/notifications/api/unread_list/"):  # Or any other condition
            del request.session
