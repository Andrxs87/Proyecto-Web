from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Categoria, Producto


def crear(nombre, categoria, precio, talla="M", activo=True, **extra):
    return Producto.objects.create(
        nombre=nombre, categoria=categoria, precio=Decimal(precio),
        talla=talla, activo=activo, **extra,
    )


class CatalogoTests(TestCase):
    def setUp(self):
        self.camisetas = Categoria.objects.create(nombre="Camisetas")
        self.jeans = Categoria.objects.create(nombre="Pantalones")
        self.c1 = crear("Camiseta blanca", self.camisetas, "35000", "M")
        self.c2 = crear("Camiseta negra", self.camisetas, "45000", "L")
        self.j1 = crear("Jean azul", self.jeans, "120000", "L", descripcion="Denim elástico")
        self.oculto = crear("Producto oculto", self.camisetas, "10000", activo=False)

    def nombres(self, respuesta):
        return [p.nombre for p in respuesta.context["pagina"]]

    def test_solo_muestra_productos_activos(self):
        resp = self.client.get(reverse("catalogo"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Producto oculto", self.nombres(resp))
        self.assertEqual(resp.context["total"], 3)

    def test_filtra_por_categoria(self):
        resp = self.client.get(reverse("catalogo"), {"categoria": self.jeans.pk})
        self.assertEqual(self.nombres(resp), ["Jean azul"])

    def test_filtra_por_talla(self):
        resp = self.client.get(reverse("catalogo"), {"talla": "L"})
        self.assertCountEqual(self.nombres(resp), ["Camiseta negra", "Jean azul"])

    def test_filtra_por_rango_de_precio(self):
        resp = self.client.get(reverse("catalogo"), {"precio_min": "40000", "precio_max": "100000"})
        self.assertEqual(self.nombres(resp), ["Camiseta negra"])

    def test_busca_por_nombre_y_descripcion(self):
        resp = self.client.get(reverse("catalogo"), {"q": "blanca"})
        self.assertEqual(self.nombres(resp), ["Camiseta blanca"])
        resp = self.client.get(reverse("catalogo"), {"q": "denim"})
        self.assertEqual(self.nombres(resp), ["Jean azul"])

    def test_ordena_por_precio(self):
        resp = self.client.get(reverse("catalogo"), {"orden": "precio_desc"})
        self.assertEqual(self.nombres(resp)[0], "Jean azul")
        resp = self.client.get(reverse("catalogo"), {"orden": "precio_asc"})
        self.assertEqual(self.nombres(resp)[0], "Camiseta blanca")

    def test_filtros_invalidos_no_rompen_la_pagina(self):
        resp = self.client.get(reverse("catalogo"), {"precio_min": "abc", "categoria": "999"})
        self.assertEqual(resp.status_code, 200)

    def test_paginacion_conserva_filtros(self):
        for i in range(8):
            crear(f"Gorra {i}", self.camisetas, "20000", "M")
        resp = self.client.get(reverse("catalogo"), {"categoria": self.camisetas.pk})
        self.assertEqual(len(resp.context["pagina"]), 6)
        self.assertContains(resp, f"categoria={self.camisetas.pk}&page=2")
        resp2 = self.client.get(reverse("catalogo"), {"categoria": self.camisetas.pk, "page": 2})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.context["pagina"]), 4)

    def test_peticion_fetch_devuelve_solo_el_fragmento(self):
        resp = self.client.get(reverse("catalogo"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "<html")
        self.assertContains(resp, "Camiseta blanca")

    def test_marca_productos_agotados(self):
        resp = self.client.get(reverse("catalogo"))
        self.assertContains(resp, "Agotado")  # stock inicial = 0

    def test_formato_de_precio_colombiano(self):
        resp = self.client.get(reverse("catalogo"))
        self.assertContains(resp, "$120.000")


class DetalleYHomeTests(TestCase):
    def setUp(self):
        self.cat = Categoria.objects.create(nombre="Camisetas")
        self.m = crear("Camiseta oversize", self.cat, "89900", "M")
        self.l = crear("Camiseta oversize", self.cat, "89900", "L")
        self.oculto = crear("Oculto", self.cat, "10000", activo=False)

    def test_detalle_muestra_producto_y_otras_tallas(self):
        resp = self.client.get(reverse("detalle_producto", args=[self.m.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Camiseta oversize")
        self.assertContains(resp, "Otras tallas")
        self.assertContains(resp, reverse("detalle_producto", args=[self.l.pk]))

    def test_detalle_de_producto_inactivo_da_404(self):
        resp = self.client.get(reverse("detalle_producto", args=[self.oculto.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_detalle_inexistente_da_404(self):
        self.assertEqual(self.client.get(reverse("detalle_producto", args=[9999])).status_code, 404)

    def test_home_muestra_categorias_y_destacados(self):
        resp = self.client.get(reverse("inicio"))
        self.assertContains(resp, "Camisetas")
        self.assertContains(resp, "Camiseta oversize")
        self.assertNotContains(resp, "Oculto")
