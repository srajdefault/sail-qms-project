from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def role_required(allowed_roles=[]):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Superusers always have full access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            profile = getattr(request.user, 'operator_profile', None)
            if profile and profile.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, "Access Denied: You do not have permission for this portal.")
            
            # Redirect to their appropriate home
            if profile and profile.role == 'OPERATOR':
                return redirect('operator_submit')
            elif profile and profile.role == 'SUPERVISOR':
                return redirect('supervisor_dashboard')
            elif profile and profile.role == 'MANAGER':
                return redirect('manager_overview')
            
            return redirect('login')
        return _wrapped_view
    return decorator