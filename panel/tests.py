import io
import shutil
import tempfile
from decimal import Decimal

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Sum
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from catalogo.models import Categoria, MovimientoStock, Producto
from catalogo.servicios import ajustar_stock
from cuentas.models import Usuario
from pedidos.models import Carrito, ItemCarrito, Pedido
from pedidos.servicios import PedidoInvalido, cambiar_estado, crear_pedido


class PanelBase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            "adm", "adm@correo.com", "x12345678", is_staff=True
        )
        self.cliente = Usuario.objects.create_user("cli", "cli@correo.com", "x12345678")
        self.cat = Categoria.objects.create(nombre="Camisetas")
        self.camiseta = Producto.objects.create(
            nombre="Camiseta", categoria=self.cat, precio=Decimal("50000")
        )
        ajustar_stock(self.camiseta.pk, 10, MovimientoStock.Tipo.ENTRADA, self.admin, "Inicial")
        self.client.force_login(self.admin)

    def stock(self, producto):
        producto.refresh_from_db()
        return producto.stock

    def hacer_pedido(self, cantidad=2):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.cliente)
        ItemCarrito.objects.create(carrito=carrito, producto=self.camiseta, cantidad=cantidad)
        return crear_pedido(self.cliente, "Calle 1 # 2-3")


class PermisosTests(PanelBase):
    def urls(self):
        pk = self.camiseta.pk
        pedido = self.hacer_pedido()
        return [
            reverse("panel_inicio"), reverse("panel_productos"),
            reverse("panel_producto_nuevo"), reverse("panel_producto_editar", args=[pk]),
            reverse("panel_producto_stock", args=[pk]), reverse("panel_categorias"),
            reverse("panel_categoria_nueva"), reverse("panel_pedidos"),
            reverse("panel_pedido_detalle", args=[pedido.pk]), reverse("panel_historial"),
        ]

    def test_visitante_es_enviado_al_login(self):
        urls = self.urls()
        self.client.logout()
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, url)
            self.assertIn("/cuentas/login/", resp.url)

    def test_cliente_recibe_403_en_todo_el_panel(self):
        urls = self.urls()
        self.client.force_login(self.cliente)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_cliente_no_puede_ejecutar_acciones(self):
        pk = self.camiseta.pk
        self.client.force_login(self.cliente)
        self.assertEqual(self.client.post(reverse("panel_producto_toggle", args=[pk])).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("panel_producto_stock", args=[pk]),
                {"tipo": "ajuste", "cantidad": -5, "motivo": "robo"},
            ).status_code, 403,
        )
        self.assertEqual(self.stock(self.camiseta), 10)
        self.assertTrue(Producto.objects.get(pk=pk).activo)

    def test_admin_ve_el_panel(self):
        for nombre in ("panel_productos", "panel_categorias", "panel_pedidos", "panel_historial"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_acciones_solo_por_post(self):
        pk = self.camiseta.pk
        self.assertEqual(self.client.get(reverse("panel_producto_toggle", args=[pk])).status_code, 405)


class ProductosTests(PanelBase):
    DATOS = {
        "categoria": "", "nombre": "Buzo", "descripcion": "Algodón", "precio": "139900",
        "talla": "L", "activo": "on", "stock_inicial": "7",
    }

    def datos(self, **cambios):
        return {**self.DATOS, "categoria": self.cat.pk, **cambios}

    def test_crear_producto_con_stock_inicial_deja_historial(self):
        resp = self.client.post(reverse("panel_producto_nuevo"), self.datos())
        self.assertRedirects(resp, reverse("panel_productos"))
        producto = Producto.objects.get(nombre="Buzo")
        self.assertEqual(producto.stock, 7)
        mov = producto.movimientos.get()
        self.assertEqual((mov.tipo, mov.cantidad, mov.usuario), ("entrada", 7, self.admin))
        self.assertEqual(mov.motivo, "Stock inicial")

    def test_crear_producto_sin_stock_no_genera_movimiento(self):
        self.client.post(reverse("panel_producto_nuevo"), self.datos(stock_inicial="0"))
        producto = Producto.objects.get(nombre="Buzo")
        self.assertEqual(producto.stock, 0)
        self.assertFalse(producto.movimientos.exists())

    def test_precio_negativo_es_invalido(self):
        resp = self.client.post(reverse("panel_producto_nuevo"), self.datos(precio="-5"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Producto.objects.filter(nombre="Buzo").exists())

    def test_editar_no_permite_cambiar_el_stock(self):
        resp = self.client.post(
            reverse("panel_producto_editar", args=[self.camiseta.pk]),
            self.datos(nombre="Camiseta nueva", stock="9999", stock_inicial="9999"),
        )
        self.assertRedirects(resp, reverse("panel_productos"))
        self.camiseta.refresh_from_db()
        self.assertEqual(self.camiseta.nombre, "Camiseta nueva")
        self.assertEqual(self.camiseta.stock, 10)  # el stock sigue intacto

    def test_activar_y_desactivar(self):
        self.client.post(reverse("panel_producto_toggle", args=[self.camiseta.pk]))
        self.camiseta.refresh_from_db()
        self.assertFalse(self.camiseta.activo)
        self.assertEqual(self.client.get(reverse("catalogo")).context["total"], 0)  # oculto del catálogo
        self.client.post(reverse("panel_producto_toggle", args=[self.camiseta.pk]))
        self.camiseta.refresh_from_db()
        self.assertTrue(self.camiseta.activo)
        self.assertEqual(self.client.get(reverse("catalogo")).context["total"], 1)

    def test_busqueda_en_la_lista(self):
        Producto.objects.create(nombre="Jean", categoria=self.cat, precio=Decimal("1"))
        resp = self.client.get(reverse("panel_productos"), {"q": "jean"})
        self.assertEqual([p.nombre for p in resp.context["pagina"]], ["Jean"])

    def test_subir_imagen(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(buffer, "PNG")
        imagen = SimpleUploadedFile("foto.png", buffer.getvalue(), content_type="image/png")
        with override_settings(MEDIA_ROOT=carpeta):
            self.client.post(reverse("panel_producto_nuevo"), {**self.datos(), "imagen": imagen})
        self.assertTrue(Producto.objects.get(nombre="Buzo").imagen.name.startswith("productos/"))


class AjusteStockTests(PanelBase):
    def ajustar(self, **datos):
        return self.client.post(reverse("panel_producto_stock", args=[self.camiseta.pk]), datos)

    def test_entrada_suma_y_queda_registrada(self):
        resp = self.ajustar(tipo="entrada", cantidad=5, motivo="Reposición")
        self.assertRedirects(resp, reverse("panel_productos"))
        self.assertEqual(self.stock(self.camiseta), 15)
        mov = self.camiseta.movimientos.first()
        self.assertEqual((mov.tipo, mov.cantidad, mov.stock_anterior, mov.stock_nuevo), ("entrada", 5, 10, 15))
        self.assertEqual(mov.usuario, self.admin)

    def test_ajuste_negativo_con_motivo(self):
        self.ajustar(tipo="ajuste", cantidad=-3, motivo="Prenda dañada")
        self.assertEqual(self.stock(self.camiseta), 7)
        self.assertEqual(self.camiseta.movimientos.first().motivo, "Prenda dañada")

    def test_ajuste_sin_motivo_es_invalido(self):
        resp = self.ajustar(tipo="ajuste", cantidad=-3, motivo="")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.stock(self.camiseta), 10)

    def test_no_permite_stock_negativo(self):
        resp = self.ajustar(tipo="ajuste", cantidad=-11, motivo="x")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.stock(self.camiseta), 10)

    def test_entrada_negativa_y_cantidad_cero_son_invalidas(self):
        self.ajustar(tipo="entrada", cantidad=-2, motivo="")
        self.ajustar(tipo="entrada", cantidad=0, motivo="")
        self.assertEqual(self.stock(self.camiseta), 10)
        self.assertEqual(self.camiseta.movimientos.count(), 1)  # solo el inicial

    def test_tipos_venta_y_cancelacion_no_se_aceptan_a_mano(self):
        self.ajustar(tipo="venta", cantidad=-2, motivo="x")
        self.ajustar(tipo="cancelacion", cantidad=2, motivo="x")
        self.assertEqual(self.stock(self.camiseta), 10)


class CategoriasTests(PanelBase):
    def test_crear_editar_y_eliminar(self):
        self.client.post(reverse("panel_categoria_nueva"), {"nombre": "Gorras", "descripcion": ""})
        gorras = Categoria.objects.get(nombre="Gorras")
        self.client.post(
            reverse("panel_categoria_editar", args=[gorras.pk]),
            {"nombre": "Accesorios", "descripcion": "Varios"},
        )
        gorras.refresh_from_db()
        self.assertEqual(gorras.nombre, "Accesorios")
        self.client.post(reverse("panel_categoria_eliminar", args=[gorras.pk]))
        self.assertFalse(Categoria.objects.filter(pk=gorras.pk).exists())

    def test_no_elimina_una_categoria_con_productos(self):
        resp = self.client.post(reverse("panel_categoria_eliminar", args=[self.cat.pk]), follow=True)
        self.assertTrue(Categoria.objects.filter(pk=self.cat.pk).exists())
        self.assertContains(resp, "tiene productos asociados")

    def test_nombre_repetido_es_invalido(self):
        resp = self.client.post(reverse("panel_categoria_nueva"), {"nombre": "Camisetas"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Categoria.objects.filter(nombre="Camisetas").count(), 1)


class PedidosPanelTests(PanelBase):
    def cambiar(self, pedido, estado, **extra):
        return self.client.post(reverse("panel_pedido_estado", args=[pedido.pk]), {"estado": estado, **extra})

    def test_lista_y_filtro_por_estado(self):
        pedido = self.hacer_pedido(1)
        resp = self.client.get(reverse("panel_pedidos"))
        self.assertContains(resp, f"#{pedido.pk}")
        resp = self.client.get(reverse("panel_pedidos"), {"estado": "entregado"})
        self.assertEqual(len(resp.context["pagina"]), 0)

    def test_flujo_pendiente_enviado_entregado(self):
        pedido = self.hacer_pedido()
        self.cambiar(pedido, "enviado")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "enviado")
        self.cambiar(pedido, "entregado")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "entregado")
        self.assertEqual(self.stock(self.camiseta), 8)  # el stock no se toca

    def test_cancelar_desde_el_panel_devuelve_el_stock_con_historial(self):
        pedido = self.hacer_pedido(3)
        self.assertEqual(self.stock(self.camiseta), 7)
        self.cambiar(pedido, "cancelado")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "cancelado")
        self.assertEqual(self.stock(self.camiseta), 10)
        mov = MovimientoStock.objects.get(tipo="cancelacion", pedido=pedido)
        self.assertEqual(mov.usuario, self.admin)  # queda quién canceló
        suma = self.camiseta.movimientos.aggregate(t=Sum("cantidad"))["t"]
        self.assertEqual(suma, 10)

    def test_transiciones_invalidas_se_rechazan(self):
        pedido = self.hacer_pedido()
        self.cambiar(pedido, "entregado")  # pendiente -> entregado: saltarse el envío
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "pendiente")

        self.cambiar(pedido, "enviado")
        self.cambiar(pedido, "cancelado")  # enviado -> cancelado: devolución, fuera de alcance
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "enviado")
        self.assertEqual(self.stock(self.camiseta), 8)

    def test_estados_finales_no_cambian(self):
        pedido = self.hacer_pedido()
        self.cambiar(pedido, "cancelado")
        self.cambiar(pedido, "pendiente")
        self.cambiar(pedido, "enviado")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "cancelado")
        self.assertEqual(self.stock(self.camiseta), 10)

    def test_estado_inexistente(self):
        pedido = self.hacer_pedido()
        self.cambiar(pedido, "inventado")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "pendiente")
        with self.assertRaises(PedidoInvalido):
            cambiar_estado(pedido.pk, "inventado", self.admin)

    def test_mismo_estado_no_hace_nada(self):
        pedido = self.hacer_pedido()
        self.cambiar(pedido, "pendiente")
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "pendiente")

    def test_detalle_muestra_precio_vendido_y_movimientos(self):
        pedido = self.hacer_pedido(2)
        resp = self.client.get(reverse("panel_pedido_detalle", args=[pedido.pk]))
        self.assertContains(resp, "$50.000")
        self.assertContains(resp, "$100.000")
        self.assertContains(resp, "Venta")

    def test_cambio_desde_detalle_vuelve_al_detalle(self):
        pedido = self.hacer_pedido()
        resp = self.cambiar(pedido, "enviado", volver="detalle")
        self.assertRedirects(resp, reverse("panel_pedido_detalle", args=[pedido.pk]))

    def test_django_admin_no_permite_editar_pedidos(self):
        superusuario = Usuario.objects.create_superuser("root", "root@correo.com", "x12345678")
        peticion = RequestFactory().get("/admin/")
        peticion.user = superusuario
        modelo_admin = admin.site._registry[Pedido]
        self.assertFalse(modelo_admin.has_change_permission(peticion))
        self.assertFalse(modelo_admin.has_add_permission(peticion))
        self.assertFalse(modelo_admin.has_delete_permission(peticion))


class HistorialTests(PanelBase):
    def test_lista_y_filtros(self):
        otro = Producto.objects.create(nombre="Jean", categoria=self.cat, precio=Decimal("1"))
        ajustar_stock(otro.pk, 4, MovimientoStock.Tipo.ENTRADA, self.admin)
        resp = self.client.get(reverse("panel_historial"), {"producto": self.camiseta.pk})
        self.assertEqual([m.producto for m in resp.context["pagina"]], [self.camiseta])
        resp = self.client.get(reverse("panel_historial"), {"tipo": "venta"})
        self.assertEqual(len(resp.context["pagina"]), 0)
        resp = self.client.get(reverse("panel_historial"), {"producto": "abc", "tipo": "xx"})
        self.assertEqual(resp.status_code, 200)

    def test_auditoria_sin_problemas(self):
        self.hacer_pedido()
        resp = self.client.get(reverse("panel_historial"))
        self.assertEqual(resp.context["inconsistentes"], [])
        self.assertContains(resp, "coincide con la suma de sus movimientos")

    def test_auditoria_detecta_stock_manipulado(self):
        # Alguien modifica el stock directamente en la base de datos, sin dejar movimiento
        Producto.objects.filter(pk=self.camiseta.pk).update(stock=500)
        resp = self.client.get(reverse("panel_historial"))
        self.assertEqual([p.pk for p in resp.context["inconsistentes"]], [self.camiseta.pk])
        self.assertContains(resp, "NO coincide")
        self.assertContains(resp, "stock registrado 500, según movimientos 10")
