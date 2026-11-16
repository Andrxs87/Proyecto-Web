from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalogo.models import Categoria, MovimientoStock, Producto
from catalogo.servicios import ajustar_stock
from cuentas.models import Usuario

from .models import Carrito, ItemCarrito

FETCH = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class CarritoBase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            "adm", "adm@correo.com", "x12345678", is_staff=True
        )
        self.cliente = Usuario.objects.create_user("cli", "cli@correo.com", "x12345678")
        self.otro = Usuario.objects.create_user("otro", "otro@correo.com", "x12345678")
        cat = Categoria.objects.create(nombre="Camisetas")
        self.camiseta = Producto.objects.create(
            nombre="Camiseta", categoria=cat, precio=Decimal("50000")
        )
        self.jean = Producto.objects.create(
            nombre="Jean", categoria=cat, precio=Decimal("120000"), talla="L"
        )
        self.oculto = Producto.objects.create(
            nombre="Oculto", categoria=cat, precio=Decimal("1000"), activo=False
        )
        for producto in (self.camiseta, self.jean, self.oculto):
            ajustar_stock(producto.pk, 5, MovimientoStock.Tipo.ENTRADA, self.admin)
        self.client.force_login(self.cliente)

    def agregar(self, producto, cantidad=1, **extra):
        return self.client.post(
            reverse("carrito_agregar", args=[producto.pk]), {"cantidad": cantidad}, **extra
        )


class PermisosTests(CarritoBase):
    def test_visitante_es_enviado_al_login(self):
        self.client.logout()
        resp = self.client.get(reverse("carrito"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/cuentas/login/", resp.url)
        resp = self.agregar(self.camiseta)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ItemCarrito.objects.exists())

    def test_administrador_no_puede_usar_el_carrito(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("carrito")).status_code, 403)
        self.assertEqual(self.agregar(self.camiseta).status_code, 403)

    def test_agregar_solo_acepta_post(self):
        resp = self.client.get(reverse("carrito_agregar", args=[self.camiseta.pk]))
        self.assertEqual(resp.status_code, 405)


class AgregarTests(CarritoBase):
    def test_agrega_y_acumula(self):
        self.agregar(self.camiseta, 2)
        self.agregar(self.camiseta, 1)
        item = ItemCarrito.objects.get()
        self.assertEqual(item.cantidad, 3)
        self.assertEqual(Carrito.objects.filter(usuario=self.cliente).count(), 1)

    def test_no_permite_superar_el_stock(self):
        self.agregar(self.camiseta, 4)
        self.agregar(self.camiseta, 2)  # 4 + 2 > 5
        self.assertEqual(ItemCarrito.objects.get().cantidad, 4)

    def test_cantidades_invalidas(self):
        for valor in ("0", "-3", "abc", ""):
            self.agregar(self.camiseta, valor)
        self.assertFalse(ItemCarrito.objects.exists())

    def test_producto_inactivo_da_404(self):
        self.assertEqual(self.agregar(self.oculto).status_code, 404)

    def test_agregar_con_fetch_responde_json(self):
        resp = self.agregar(self.camiseta, 2, **FETCH)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["ok"], True)
        self.assertEqual(resp.json()["items"], 1)

        resp = self.agregar(self.camiseta, 99, **FETCH)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["ok"], False)
        self.assertEqual(ItemCarrito.objects.get().cantidad, 2)

    def test_agregar_sin_fetch_redirige_al_carrito(self):
        self.assertRedirects(self.agregar(self.camiseta), reverse("carrito"))

    def test_agregar_no_toca_el_stock(self):
        self.agregar(self.camiseta, 3)
        self.camiseta.refresh_from_db()
        self.assertEqual(self.camiseta.stock, 5)  # el stock solo baja al finalizar el pedido


class ModificarCarritoTests(CarritoBase):
    def setUp(self):
        super().setUp()
        self.agregar(self.camiseta, 2)
        self.item = ItemCarrito.objects.get()

    def test_actualiza_cantidad(self):
        self.client.post(reverse("carrito_actualizar", args=[self.item.pk]), {"cantidad": 4})
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 4)

    def test_no_actualiza_por_encima_del_stock_ni_por_debajo_de_uno(self):
        for valor in (6, 0, -1):
            self.client.post(reverse("carrito_actualizar", args=[self.item.pk]), {"cantidad": valor})
        self.item.refresh_from_db()
        self.assertEqual(self.item.cantidad, 2)

    def test_quita_producto(self):
        self.client.post(reverse("carrito_quitar", args=[self.item.pk]))
        self.assertFalse(ItemCarrito.objects.exists())

    def test_no_puede_tocar_el_carrito_de_otro_usuario(self):
        self.client.force_login(self.otro)
        resp = self.client.post(reverse("carrito_quitar", args=[self.item.pk]))
        self.assertEqual(resp.status_code, 404)
        resp = self.client.post(reverse("carrito_actualizar", args=[self.item.pk]), {"cantidad": 1})
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(ItemCarrito.objects.filter(pk=self.item.pk).exists())


class VistaCarritoTests(CarritoBase):
    def test_carrito_vacio(self):
        resp = self.client.get(reverse("carrito"))
        self.assertContains(resp, "Tu carrito está vacío")

    def test_muestra_total_y_contador(self):
        self.agregar(self.camiseta, 2)   # 100.000
        self.agregar(self.jean, 1)       # 120.000
        resp = self.client.get(reverse("carrito"))
        self.assertContains(resp, "$220.000")
        self.assertEqual(resp.context["carrito_cantidad"], 2)
        self.assertEqual(resp.context["total"], Decimal("220000"))

    def test_avisa_si_un_producto_dejo_de_estar_disponible(self):
        self.agregar(self.camiseta, 1)
        Producto.objects.filter(pk=self.camiseta.pk).update(activo=False)
        resp = self.client.get(reverse("carrito"))
        self.assertTrue(resp.context["hay_problemas"])
        self.assertContains(resp, "ya no está disponible")

    def test_el_carrito_es_independiente_por_usuario(self):
        self.agregar(self.camiseta, 1)
        self.client.force_login(self.otro)
        resp = self.client.get(reverse("carrito"))
        self.assertEqual(resp.context["items"], [])

    def test_detalle_muestra_formulario_solo_al_cliente(self):
        url = reverse("detalle_producto", args=[self.camiseta.pk])
        self.assertContains(self.client.get(url), "Agregar al carrito")
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(url), "Agregar al carrito")
        self.client.logout()
        resp = self.client.get(url)
        self.assertNotContains(resp, "Agregar al carrito")
        self.assertContains(resp, "Iniciar sesión")
