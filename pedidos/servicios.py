"""Lógica de negocio de los pedidos.

Todo ocurre dentro de una transacción: o se completa el pedido entero
(detalle + descuento de stock + historial + carrito vacío) o no se guarda
nada. Así nunca queda un pedido a medias ni stock descontado sin pedido.
"""
from decimal import Decimal

from django.db import transaction

from catalogo.models import MovimientoStock
from catalogo.servicios import StockInsuficiente, ajustar_stock

from .models import Carrito, DetallePedido, Pedido


class PedidoInvalido(Exception):
    """El pedido no se puede crear o modificar (el mensaje se muestra al usuario)."""


def problema_en_items(items):
    """Devuelve un mensaje si algún ítem ya no se puede comprar, o None si todo está bien."""
    for item in items:
        producto = item.producto
        if not producto.activo:
            return f"«{producto.nombre}» ya no está disponible. Quítalo del carrito."
        if item.cantidad > producto.stock:
            return (
                f"Solo hay {producto.stock} unidad(es) de «{producto.nombre}» "
                f"y tienes {item.cantidad} en el carrito."
            )
    return None


@transaction.atomic
def crear_pedido(usuario, direccion_envio):
    """Convierte el carrito del usuario en un pedido. Devuelve el Pedido creado."""
    carrito = Carrito.objects.filter(usuario=usuario).first()
    # Se procesa siempre en el mismo orden (por producto) para evitar bloqueos cruzados
    items = (
        list(carrito.items.select_related("producto").order_by("producto_id"))
        if carrito
        else []
    )
    if not items:
        raise PedidoInvalido("Tu carrito está vacío.")

    pedido = Pedido.objects.create(
        usuario=usuario, direccion_envio=direccion_envio, total=Decimal("0")
    )

    total = Decimal("0")
    for item in items:
        if not item.producto.activo:
            raise PedidoInvalido(
                f"«{item.producto.nombre}» ya no está disponible. Quítalo del carrito."
            )
        try:
            movimiento = ajustar_stock(
                item.producto_id,
                -item.cantidad,
                MovimientoStock.Tipo.VENTA,
                usuario,
                motivo=f"Pedido #{pedido.pk}",
                pedido=pedido,
            )
        except StockInsuficiente:
            raise PedidoInvalido(
                f"No hay suficiente stock de «{item.producto.nombre}». Ajusta la cantidad en tu carrito."
            )

        # movimiento.producto se leyó con el producto bloqueado: el precio es el vigente
        precio = movimiento.producto.precio
        DetallePedido.objects.create(
            pedido=pedido,
            producto_id=item.producto_id,
            cantidad=item.cantidad,
            precio_unitario=precio,
        )
        total += precio * item.cantidad

    pedido.total = total
    pedido.save(update_fields=["total"])
    carrito.items.all().delete()
    return pedido


@transaction.atomic
def cancelar_pedido(pedido_id, usuario):
    """Cancela un pedido PENDIENTE y devuelve su stock (queda en el historial)."""
    pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
    if pedido.estado != Pedido.Estado.PENDIENTE:
        raise PedidoInvalido("Solo se pueden cancelar pedidos pendientes.")

    for detalle in pedido.detalles.order_by("producto_id"):
        ajustar_stock(
            detalle.producto_id,
            detalle.cantidad,
            MovimientoStock.Tipo.CANCELACION,
            usuario,
            motivo=f"Cancelación del pedido #{pedido.pk}",
            pedido=pedido,
        )

    pedido.estado = Pedido.Estado.CANCELADO
    pedido.save(update_fields=["estado"])
    return pedido
