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
    """Solo lectura: el estado de un pedido se cambia desde el panel del
    administrador, para que cancelar devuelva el stock y quede en el historial."""

    list_display = ("id", "usuario", "fecha_pedido", "estado", "total")
    list_filter = ("estado",)
    inlines = [DetallePedidoInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
