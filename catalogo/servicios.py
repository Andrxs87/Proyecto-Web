"""Lógica de negocio del inventario.

REGLA DEL PROYECTO: el stock de un producto solo se modifica llamando a
ajustar_stock(). Nunca hagas producto.stock = X en otro lugar.
"""
from django.db import transaction

from .models import MovimientoStock, Producto


class StockInsuficiente(Exception):
    """Se intentó dejar el stock por debajo de cero."""


@transaction.atomic
def ajustar_stock(producto_id, cantidad, tipo, usuario, motivo="", pedido=None):
    """Cambia el stock de un producto y registra el movimiento.

    cantidad: con signo (+ suma, - resta).
    tipo: uno de MovimientoStock.Tipo (entrada, venta, cancelacion, ajuste).
    Devuelve el MovimientoStock creado.
    """
    if cantidad == 0:
        raise ValueError("La cantidad no puede ser cero.")
    if tipo in (MovimientoStock.Tipo.ENTRADA, MovimientoStock.Tipo.CANCELACION) and cantidad < 0:
        raise ValueError(f"Un movimiento de tipo '{tipo}' debe sumar stock.")
    if tipo == MovimientoStock.Tipo.VENTA and cantidad > 0:
        raise ValueError("Una venta debe restar stock.")

    # select_for_update bloquea la fila para evitar que dos compras
    # simultáneas lean el mismo stock (en SQLite se ignora, en MySQL aplica).
    producto = Producto.objects.select_for_update().get(pk=producto_id)

    stock_anterior = producto.stock
    stock_nuevo = stock_anterior + cantidad
    if stock_nuevo < 0:
        raise StockInsuficiente(
            f"Stock insuficiente de '{producto}': hay {stock_anterior} "
            f"y se pidieron {abs(cantidad)}."
        )

    producto.stock = stock_nuevo
    producto.save(update_fields=["stock"])

    return MovimientoStock.objects.create(
        producto=producto,
        usuario=usuario,
        pedido=pedido,
        tipo=tipo,
        cantidad=cantidad,
        stock_anterior=stock_anterior,
        stock_nuevo=stock_nuevo,
        motivo=motivo,
    )
