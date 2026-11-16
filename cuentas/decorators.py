"""Decoradores para proteger vistas según el rol del usuario.

Uso:
    from cuentas.decorators import cliente_requerido, administrador_requerido

    @cliente_requerido
    def ver_carrito(request): ...

    @administrador_requerido
    def panel_productos(request): ...

- Visitante (sin sesión): se le envía al login (y vuelve a la página después).
- Rol equivocado: error 403 (acceso prohibido).
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def administrador_requerido(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Esta sección es solo para administradores.")
        return vista(request, *args, **kwargs)

    return envoltura


def cliente_requerido(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if request.user.is_staff:
            raise PermissionDenied("Esta sección es solo para clientes.")
        return vista(request, *args, **kwargs)

    return envoltura
