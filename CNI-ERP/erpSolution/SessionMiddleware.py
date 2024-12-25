from django.contrib.sessions.middleware import SessionMiddleware
from django.shortcuts import redirect
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin

import datetime
from django.contrib.auth import logout
from django.utils.timezone import now

class SessionMiddleware(SessionMiddleware):
    def process_request(self, request):
        if request.path.startswith("/inbox/notifications/api/unread_list/"):  # Or any other condition
            del request.session
    
class DynamicTwoFactorRememberMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Example: Set the cookie age based on some condition
        # print("------------------set remember time-------------------")
        # Get the current time with the local timezone
        current_time = timezone.localtime()

        # Calculate midnight in the local timezone
        midnight = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # Calculate the time remaining until midnight
        time_until_midnight = midnight - current_time
        max_age=int(time_until_midnight.total_seconds())
        settings.TWO_FACTOR_REMEMBER_COOKIE_AGE=max_age


class AutoLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ignore logout for unauthenticated users
        if request.user.is_authenticated:
            current_time = now()

            # Exclude specific URLs or request methods from updating session time
            excluded_paths = [
                '/inbox/notifications/api/unread_list',  
            ]
            # Exclude requests with certain paths
            if not any(request.path.startswith(path) for path in excluded_paths):
                # Retrieve the last activity time from the session and convert it from string to datetime
                last_activity_str = request.session.get('last_activity')
                if last_activity_str:
                    last_activity = datetime.datetime.fromisoformat(last_activity_str)
                else:
                    last_activity = current_time

                # Calculate the elapsed time since the last activity
                elapsed_time = (current_time - last_activity).total_seconds()

                # Logout if inactive for more than AUTO_LOGOUT_DELAY seconds
                if elapsed_time > settings.AUTO_LOGOUT_DELAY:
                    logout(request)
                    request.session.flush()  # Clear session data
                else:
                    # Update last activity time in the session
                    request.session['last_activity'] = current_time.isoformat()

        response = self.get_response(request)
        return response