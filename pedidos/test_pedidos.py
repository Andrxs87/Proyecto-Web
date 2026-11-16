from decimal import Decimal

from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, MovimientoStock, Producto
from catalogo.servicios import ajustar_stock
from cuentas.models import Usuario

from .models import Carrito, ItemCarrito, Pedido

DIRECCION = "Calle 10 # 5-20, Bucaramanga"


class PedidosBase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            "adm", "adm@correo.com", "x12345678", is_staff=True
        )
        self.cliente = Usuario.objects.create_user("cli", "cli@correo.com", "x12345678")
        self.otro = Usuario.objects.create_user("otro", "otro@correo.com", "x12345678")
        cat = Categoria.objects.create(nombre="Ropa")
        self.camiseta = Producto.objects.create(
            nombre="Camiseta", categoria=cat, precio=Decimal("50000")
        )
        self.jean = Producto.objects.create(
            nombre="Jean", categoria=cat, precio=Decimal("120000"), talla="L"
        )
        for producto in (self.camiseta, self.jean):
            ajustar_stock(producto.pk, 5, MovimientoStock.Tipo.ENTRADA, self.admin)
        self.client.force_login(self.cliente)

    def llenar_carrito(self, usuario=None, camiseta=2, jean=1):
        carrito, _ = Carrito.objects.get_or_create(usuario=usuario or self.cliente)
        ItemCarrito.objects.create(carrito=carrito, producto=self.camiseta, cantidad=camiseta)
        ItemCarrito.objects.create(carrito=carrito, producto=self.jean, cantidad=jean)

    def finalizar(self, direccion=DIRECCION):
        return self.client.post(reverse("finalizar_pedido"), {"direccion_envio": direccion})

    def stock(self, producto):
        producto.refresh_from_db()
        return producto.stock


class PermisosTests(PedidosBase):
    def test_visitante_va_al_login(self):
        self.client.logout()
        for nombre in ("mis_pedidos", "finalizar_pedido"):
            resp = self.client.get(reverse(nombre))
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/cuentas/login/", resp.url)

    def test_administrador_recibe_403(self):
        self.client.force_login(self.admin)
        for nombre in ("mis_pedidos", "finalizar_pedido"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)


class FinalizarPedidoTests(PedidosBase):
    def test_carrito_vacio_no_permite_finalizar(self):
        resp = self.client.get(reverse("finalizar_pedido"))
        self.assertRedirects(resp, reverse("carrito"))
        self.assertEqual(self.finalizar().status_code, 302)
        self.assertFalse(Pedido.objects.exists())

    def test_pantalla_de_confirmacion(self):
        self.llenar_carrito()
        resp = self.client.get(reverse("finalizar_pedido"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "$220.000")

    def test_pedido_exitoso(self):
        self.llenar_carrito(camiseta=2, jean=1)
        resp = self.finalizar()
        pedido = Pedido.objects.get()
        self.assertRedirects(resp, reverse("pedido_detalle", args=[pedido.pk]))

        self.assertEqual(pedido.usuario, self.cliente)
        self.assertEqual(pedido.estado, Pedido.Estado.PENDIENTE)
        self.assertEqual(pedido.direccion_envio, DIRECCION)
        self.assertEqual(pedido.total, Decimal("220000"))
        self.assertEqual(pedido.detalles.count(), 2)
        # el carrito queda vacío
        self.assertFalse(ItemCarrito.objects.filter(carrito__usuario=self.cliente).exists())
        # el stock bajó
        self.assertEqual(self.stock(self.camiseta), 3)
        self.assertEqual(self.stock(self.jean), 4)

    def test_la_venta_queda_en_el_historial_de_stock(self):
        self.llenar_carrito(camiseta=2, jean=1)
        self.finalizar()
        pedido = Pedido.objects.get()
        ventas = MovimientoStock.objects.filter(tipo="venta", pedido=pedido)
        self.assertEqual(ventas.count(), 2)
        mov = ventas.get(producto=self.camiseta)
        self.assertEqual((mov.cantidad, mov.stock_anterior, mov.stock_nuevo), (-2, 5, 3))
        self.assertEqual(mov.usuario, self.cliente)

    def test_el_stock_siempre_cuadra_con_el_historial(self):
        self.llenar_carrito()
        self.finalizar()
        for producto in (self.camiseta, self.jean):
            suma = producto.movimientos.aggregate(t=Sum("cantidad"))["t"]
            self.assertEqual(suma, self.stock(producto))

    def test_el_precio_queda_congelado_en_el_pedido(self):
        self.llenar_carrito(camiseta=1, jean=0 + 1)
        self.finalizar()
        Producto.objects.filter(pk=self.camiseta.pk).update(precio=Decimal("99999"))
        pedido = Pedido.objects.get()
        detalle = pedido.detalles.get(producto=self.camiseta)
        self.assertEqual(detalle.precio_unitario, Decimal("50000"))
        self.assertEqual(pedido.total, Decimal("170000"))

    def test_direccion_obligatoria(self):
        self.llenar_carrito()
        resp = self.finalizar(direccion="")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Pedido.objects.exists())
        self.assertEqual(self.stock(self.camiseta), 5)

    def test_stock_insuficiente_no_deja_nada_a_medias(self):
        """Si un producto falla, NINGÚN producto se descuenta ni se crea el pedido."""
        self.llenar_carrito(camiseta=2, jean=3)
        # Otro cliente compra antes y deja 1 jean disponible
        ajustar_stock(self.jean.pk, -4, MovimientoStock.Tipo.AJUSTE, self.admin, "prueba")
        movimientos_antes = MovimientoStock.objects.count()

        resp = self.finalizar()
        self.assertRedirects(resp, reverse("carrito"))
        self.assertFalse(Pedido.objects.exists())
        self.assertEqual(self.stock(self.camiseta), 5)  # la camiseta no se descontó
        self.assertEqual(self.stock(self.jean), 1)
        self.assertEqual(MovimientoStock.objects.count(), movimientos_antes)
        self.assertEqual(ItemCarrito.objects.filter(carrito__usuario=self.cliente).count(), 2)

    def test_producto_desactivado_bloquea_el_pedido(self):
        self.llenar_carrito()
        Producto.objects.filter(pk=self.jean.pk).update(activo=False)
        resp = self.finalizar()
        self.assertRedirects(resp, reverse("carrito"))
        self.assertFalse(Pedido.objects.exists())
        self.assertEqual(self.stock(self.camiseta), 5)

    def test_doble_envio_no_duplica_el_pedido(self):
        self.llenar_carrito()
        self.finalizar()
        self.finalizar()  # el carrito ya está vacío
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(self.stock(self.camiseta), 3)

    def test_boton_finalizar_en_el_carrito(self):
        self.llenar_carrito()
        self.assertContains(self.client.get(reverse("carrito")), "Finalizar pedido")
        Producto.objects.filter(pk=self.jean.pk).update(activo=False)
        self.assertNotContains(self.client.get(reverse("carrito")), "Finalizar pedido")


class HistorialTests(PedidosBase):
    def crear_pedido_de(self, usuario):
        self.client.force_login(usuario)
        self.llenar_carrito(usuario=usuario, camiseta=1, jean=1)
        self.finalizar()
        return Pedido.objects.filter(usuario=usuario).latest("id")

    def test_lista_solo_mis_pedidos(self):
        mio = self.crear_pedido_de(self.cliente)
        ajeno = self.crear_pedido_de(self.otro)
        self.client.force_login(self.cliente)
        resp = self.client.get(reverse("mis_pedidos"))
        self.assertContains(resp, f"#{mio.pk}")
        self.assertNotContains(resp, f"#{ajeno.pk}<")

    def test_no_se_puede_ver_el_pedido_de_otro(self):
        ajeno = self.crear_pedido_de(self.otro)
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.get(reverse("pedido_detalle", args=[ajeno.pk])).status_code, 404)

    def test_detalle_muestra_productos_y_total(self):
        pedido = self.crear_pedido_de(self.cliente)
        resp = self.client.get(reverse("pedido_detalle", args=[pedido.pk]))
        self.assertContains(resp, "Camiseta")
        self.assertContains(resp, "$170.000")
        self.assertContains(resp, "Cancelar pedido")


class CancelarPedidoTests(PedidosBase):
    def setUp(self):
        super().setUp()
        self.llenar_carrito(camiseta=2, jean=1)
        self.finalizar()
        self.pedido = Pedido.objects.get()

    def cancelar(self, pedido=None):
        return self.client.post(reverse("pedido_cancelar", args=[(pedido or self.pedido).pk]))

    def test_cancelar_devuelve_el_stock_y_queda_en_el_historial(self):
        self.cancelar()
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.CANCELADO)
        self.assertEqual(self.stock(self.camiseta), 5)
        self.assertEqual(self.stock(self.jean), 5)
        cancelaciones = MovimientoStock.objects.filter(tipo="cancelacion", pedido=self.pedido)
        self.assertEqual(cancelaciones.count(), 2)
        for producto in (self.camiseta, self.jean):
            suma = producto.movimientos.aggregate(t=Sum("cantidad"))["t"]
            self.assertEqual(suma, self.stock(producto))

    def test_cancelar_dos_veces_no_devuelve_stock_doble(self):
        self.cancelar()
        self.cancelar()
        self.assertEqual(self.stock(self.camiseta), 5)

    def test_no_se_cancela_un_pedido_enviado(self):
        Pedido.objects.filter(pk=self.pedido.pk).update(estado=Pedido.Estado.ENVIADO)
        self.cancelar()
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.ENVIADO)
        self.assertEqual(self.stock(self.camiseta), 3)

    def test_no_se_cancela_el_pedido_de_otro(self):
        self.client.force_login(self.otro)
        self.assertEqual(self.cancelar().status_code, 404)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.PENDIENTE)

    def test_cancelar_solo_acepta_post(self):
        resp = self.client.get(reverse("pedido_cancelar", args=[self.pedido.pk]))
        self.assertEqual(resp.status_code, 405)
