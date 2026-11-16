from django.urls import path

from . import views

urlpatterns = [
    path("", views.ver_carrito, name="carrito"),
    path("agregar/<int:producto_id>/", views.agregar, name="carrito_agregar"),
    path("item/<int:item_id>/actualizar/", views.actualizar, name="carrito_actualizar"),
    path("item/<int:item_id>/quitar/", views.quitar, name="carrito_quitar"),
]
