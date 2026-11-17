from io import StringIO

from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase

from catalogo.models import MovimientoStock, Producto
from pedidos.models import Pedido


class CargarDatosTests(TestCase):
    def cargar(self):
        call_command("cargar_datos", stdout=StringIO())

    def test_carga_usuarios_productos_y_pedidos_de_ejemplo(self):
        self.cargar()
        self.assertEqual(Producto.objects.count(), 14)
        estados = sorted(Pedido.objects.values_list("estado", flat=True))
        self.assertEqual(estados, ["cancelado", "entregado", "enviado", "pendiente"])

    def test_se_puede_ejecutar_varias_veces_sin_duplicar(self):
        self.cargar()
        pedidos, movimientos = Pedido.objects.count(), MovimientoStock.objects.count()
        self.cargar()
        self.assertEqual(Pedido.objects.count(), pedidos)
        self.assertEqual(MovimientoStock.objects.count(), movimientos)

    def test_el_stock_de_los_datos_de_prueba_cuadra_con_el_historial(self):
        self.cargar()
        for producto in Producto.objects.all():
            suma = producto.movimientos.aggregate(t=Sum("cantidad"))["t"] or 0
            self.assertEqual(suma, producto.stock, producto)
