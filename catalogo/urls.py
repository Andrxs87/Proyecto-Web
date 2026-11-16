from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("catalogo/", views.lista_productos, name="catalogo"),
    path("producto/<int:pk>/", views.detalle_producto, name="detalle_producto"),
]
