from django.urls import path

from . import views

urlpatterns = [
    # Carrito
    path("carrito/", views.ver_carrito, name="carrito"),
    path("carrito/agregar/<int:producto_id>/", views.agregar, name="carrito_agregar"),
    path("carrito/item/<int:item_id>/actualizar/", views.actualizar, name="carrito_actualizar"),
    path("carrito/item/<int:item_id>/quitar/", views.quitar, name="carrito_quitar"),
    # Pedidos
    path("pedidos/", views.mis_pedidos, name="mis_pedidos"),
    path("pedidos/finalizar/", views.finalizar, name="finalizar_pedido"),
    path("pedidos/<int:pk>/", views.detalle_pedido, name="pedido_detalle"),
    path("pedidos/<int:pk>/cancelar/", views.cancelar, name="pedido_cancelar"),
]
