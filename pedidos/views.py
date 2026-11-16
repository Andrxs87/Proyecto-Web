from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogo.models import Producto
from cuentas.decorators import cliente_requerido

from .models import Carrito, ItemCarrito


def obtener_carrito(usuario):
    """Cada cliente tiene un solo carrito; se crea la primera vez que lo usa."""
    carrito, _ = Carrito.objects.get_or_create(usuario=usuario)
    return carrito


def _es_fetch(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _leer_cantidad(request):
    try:
        return int(request.POST.get("cantidad", 1))
    except (TypeError, ValueError):
        return 0


@cliente_requerido
def ver_carrito(request):
    carrito = obtener_carrito(request.user)
    items = list(carrito.items.select_related("producto").order_by("id"))
    total = sum(item.subtotal for item in items)
    hay_problemas = any(
        (not item.producto.activo) or item.cantidad > item.producto.stock
        for item in items
    )
    return render(
        request,
        "pedidos/carrito.html",
        {"items": items, "total": total, "hay_problemas": hay_problemas},
    )


@cliente_requerido
@require_POST
def agregar(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id, activo=True)
    cantidad = _leer_cantidad(request)
    carrito = obtener_carrito(request.user)
    item = ItemCarrito.objects.filter(carrito=carrito, producto=producto).first()
    en_carrito = item.cantidad if item else 0

    error = None
    if cantidad < 1:
        error = "La cantidad debe ser al menos 1."
    elif en_carrito + cantidad > producto.stock:
        error = f"Solo hay {producto.stock} unidad(es) disponible(s)."
        if en_carrito:
            error += f" Ya tienes {en_carrito} en tu carrito."

    if error:
        return _responder(request, False, error, redirect("detalle_producto", pk=producto.pk))

    if item:
        item.cantidad += cantidad
        item.save(update_fields=["cantidad"])
    else:
        ItemCarrito.objects.create(carrito=carrito, producto=producto, cantidad=cantidad)

    return _responder(
        request, True, f"«{producto.nombre}» se agregó a tu carrito.", redirect("carrito")
    )


@cliente_requerido
@require_POST
def actualizar(request, item_id):
    # Solo se puede modificar un ítem del propio carrito (si no, 404)
    item = get_object_or_404(
        ItemCarrito.objects.select_related("producto"),
        pk=item_id,
        carrito__usuario=request.user,
    )
    cantidad = _leer_cantidad(request)

    if cantidad < 1:
        messages.error(request, "La cantidad debe ser al menos 1. Usa ✕ para quitar el producto.")
    elif cantidad > item.producto.stock:
        messages.error(request, f"Solo hay {item.producto.stock} unidad(es) disponible(s).")
    else:
        item.cantidad = cantidad
        item.save(update_fields=["cantidad"])
    return redirect("carrito")


@cliente_requerido
@require_POST
def quitar(request, item_id):
    item = get_object_or_404(ItemCarrito, pk=item_id, carrito__usuario=request.user)
    nombre = item.producto.nombre
    item.delete()
    messages.success(request, f"Quitaste «{nombre}» del carrito.")
    return redirect("carrito")


def _responder(request, ok, mensaje, destino):
    """Responde en JSON si la petición viene de fetch; si no, con mensaje y redirección."""
    if _es_fetch(request):
        items = ItemCarrito.objects.filter(carrito__usuario=request.user).count()
        return JsonResponse(
            {"ok": ok, "mensaje": mensaje, "items": items}, status=200 if ok else 400
        )
    (messages.success if ok else messages.error)(request, mensaje)
    return destino
