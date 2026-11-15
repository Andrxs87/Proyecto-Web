from django.contrib import admin

from .models import Carrito, DetallePedido, ItemCarrito, Pedido


class ItemCarritoInline(admin.TabularInline):
    model = ItemCarrito
    extra = 0


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "fecha_creacion")
    inlines = [ItemCarritoInline]


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "fecha_pedido", "estado", "total")
    list_filter = ("estado",)
    inlines = [DetallePedidoInline]
