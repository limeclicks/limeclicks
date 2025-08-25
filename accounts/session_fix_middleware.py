"""
Session fix middleware to ensure proper session handling after login
"""
from django.utils.deprecation import MiddlewareMixin


class SessionFixMiddleware(MiddlewareMixin):
    """
    Middleware to fix session issues after login.
    Ensures the session is properly saved and cookies are set correctly.
    """
    
    def process_response(self, request, response):
        # If user just logged in (session was modified), ensure it's saved
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(request, 'session') and request.session.modified:
                request.session.save()
        
        # For dashboard views, add no-cache headers
        if request.path == '/accounts/dashboard/' and request.user.is_authenticated:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
        return response