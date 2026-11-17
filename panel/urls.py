from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="panel_inicio"),
    # Productos
    path("productos/", views.productos, name="panel_productos"),
    path("productos/nuevo/", views.producto_nuevo, name="panel_producto_nuevo"),
    path("productos/<int:pk>/editar/", views.producto_editar, name="panel_producto_editar"),
    path("productos/<int:pk>/activar/", views.producto_toggle, name="panel_producto_toggle"),
    path("productos/<int:pk>/stock/", views.producto_stock, name="panel_producto_stock"),
    # Categorías
    path("categorias/", views.categorias, name="panel_categorias"),
    path("categorias/nueva/", views.categoria_nueva, name="panel_categoria_nueva"),
    path("categorias/<int:pk>/editar/", views.categoria_editar, name="panel_categoria_editar"),
    path("categorias/<int:pk>/eliminar/", views.categoria_eliminar, name="panel_categoria_eliminar"),
    # Pedidos
    path("pedidos/", views.pedidos, name="panel_pedidos"),
    path("pedidos/<int:pk>/", views.pedido_detalle, name="panel_pedido_detalle"),
    path("pedidos/<int:pk>/estado/", views.pedido_estado, name="panel_pedido_estado"),
    # Historial de stock
    path("historial/", views.historial, name="panel_historial"),
]
