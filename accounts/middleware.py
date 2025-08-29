from django.contrib import messages
from django.shortcuts import redirect


class AuthenticationMiddleware:
    """
    Middleware to handle authentication requirements for the entire application.
    Redirects unauthenticated users to login page with appropriate messages.
    """
    
    # URLs that don't require authentication
    PUBLIC_URLS = [
        '/accounts/login/',
        '/accounts/register/',
        '/accounts/logout/',
        '/accounts/password-reset/',
        '/accounts/password-reset/success/',
        '/accounts/password-reset/confirm/',
        '/accounts/verify-email/',
        '/accounts/resend-confirmation/',
        '/accounts/resend-confirmation/success/',
        '/accounts/registration/success/',
        '/accounts/login-redirect/',  # Add login redirect page
        '/admin/',
        '/static/',
        '/media/',
        '/',  # Root URL
    ]
    
    # URL prefixes that don't require authentication
    PUBLIC_PREFIXES = [
        '/accounts/verify-email/',
        '/accounts/password-reset/confirm/',
        '/admin/',
        '/static/',
        '/media/',
        '/api/public/',  # For future public API endpoints
        '/project/favicon/',  # Favicon proxy is public
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if the current path requires authentication
        path = request.path
        
        # Skip authentication check for public URLs
        if self._is_public_url(path):
            return self.get_response(request)
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            # Store the intended URL for post-login redirect
            if request.method == 'GET':
                request.session['next_url'] = request.get_full_path()
            
            # Add informative message based on the path
            message = self._get_redirect_message(path)
            messages.info(request, message)
            
            # Redirect to login
            return redirect('accounts:login')
        
        response = self.get_response(request)
        return response
    
    def _is_public_url(self, path):
        """Check if the URL is public (doesn't require authentication)"""
        # Check exact matches
        if path in self.PUBLIC_URLS:
            return True
        
        # Check prefixes
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True
        
        return False
    
    def _get_redirect_message(self, path):
        """Get appropriate message based on the path being accessed"""
        messages_map = {
            '/accounts/dashboard/': 'Please sign in to access your dashboard.',
            '/accounts/settings/': 'Please sign in to manage your account settings.',
            '/project/': 'Please sign in to manage your projects.',
            '/analytics/': 'Please sign in to view analytics.',
            '/links/': 'Please sign in to manage your links.',
        }
        
        # Check for specific path messages
        for url_prefix, message in messages_map.items():
            if path.startswith(url_prefix):
                return message
        
        # Default message
        return 'Please sign in to continue.'