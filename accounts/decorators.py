from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def login_required_with_message(message="Please sign in to access this page."):
    """
    Custom login required decorator that adds a message before redirecting to login.
    
    Usage:
        @login_required_with_message()
        def my_view(request):
            ...
            
        @login_required_with_message(message="Custom message here")
        def another_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.info(request, message)
                # Store the intended URL in session for post-login redirect
                request.session['next_url'] = request.get_full_path()
                return redirect('accounts:login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Convenience decorator with default message
login_required_message = login_required_with_message()