from .models import ItemCarrito


def carrito(request):
    """Disponible en todas las plantillas como {{ carrito_cantidad }}.

    Cuenta los productos distintos en el carrito del cliente (0 para
    visitantes y administradores).
    """
    cantidad = 0
    usuario = request.user
    if usuario.is_authenticated and not usuario.is_staff:
        cantidad = ItemCarrito.objects.filter(carrito__usuario=usuario).count()
    return {"carrito_cantidad": cantidad}
