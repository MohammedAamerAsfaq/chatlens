from rest_framework.permissions import BasePermission


class HasApiScope(BasePermission):
    """Require the authenticated API key to carry the view's declared scope."""

    def has_permission(self, request, view):
        api_key = getattr(request, 'auth', None)
        if api_key is None:
            return False
        required_scope = getattr(view, 'required_scope', None)
        if required_scope is None:
            return False
        return required_scope in (api_key.scopes or [])
