from django.contrib import admin

from .models import Categoria, MovimientoStock, Producto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion")
    search_fields = ("nombre",)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "talla", "precio", "stock", "activo")
    list_filter = ("categoria", "talla", "activo")
    search_fields = ("nombre",)
    readonly_fields = ("stock", "fecha_creacion")


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    """Historial de solo lectura: no se puede crear, editar ni borrar."""

    list_display = (
        "fecha", "producto", "tipo", "cantidad",
        "stock_anterior", "stock_nuevo", "usuario", "pedido",
    )
    list_filter = ("tipo", "producto")
    search_fields = ("producto__nombre", "motivo")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
