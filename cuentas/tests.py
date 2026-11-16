from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .decorators import administrador_requerido, cliente_requerido
from .models import Usuario

DATOS_REGISTRO = {
    "username": "maria",
    "first_name": "María",
    "last_name": "Gómez",
    "email": "maria@correo.com",
    "telefono": "3001234567",
    "direccion": "Calle 1 # 2-3",
    "password1": "ClaveSegura#2026",
    "password2": "ClaveSegura#2026",
}


class RegistroYSesionTests(TestCase):
    def test_registro_crea_cliente_y_abre_sesion(self):
        resp = self.client.post(reverse("registro"), DATOS_REGISTRO)
        self.assertRedirects(resp, reverse("inicio"))
        usuario = Usuario.objects.get(username="maria")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_registro_no_permite_hacerse_administrador(self):
        datos = {**DATOS_REGISTRO, "is_staff": "on", "is_superuser": "on"}
        self.client.post(reverse("registro"), datos)
        usuario = Usuario.objects.get(username="maria")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)

    def test_registro_rechaza_correo_repetido(self):
        Usuario.objects.create_user("otro", "maria@correo.com", "x12345678")
        resp = self.client.post(reverse("registro"), DATOS_REGISTRO)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username="maria").exists())

    def test_login_y_logout(self):
        Usuario.objects.create_user("ana", "ana@correo.com", "ClaveSegura#2026")
        resp = self.client.post(
            reverse("login"), {"username": "ana", "password": "ClaveSegura#2026"}
        )
        self.assertRedirects(resp, reverse("inicio"))
        self.assertIn("_auth_user_id", self.client.session)

        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_con_clave_incorrecta(self):
        Usuario.objects.create_user("ana", "ana@correo.com", "ClaveSegura#2026")
        resp = self.client.post(reverse("login"), {"username": "ana", "password": "mala"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_paginas_publicas_cargan(self):
        for nombre in ("inicio", "login", "registro"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)


class RolesTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.cliente = Usuario.objects.create_user("cli", "cli@correo.com", "x12345678")
        self.admin = Usuario.objects.create_user(
            "adm", "adm@correo.com", "x12345678", is_staff=True
        )

        @cliente_requerido
        def vista_cliente(request):
            return HttpResponse("ok")

        @administrador_requerido
        def vista_admin(request):
            return HttpResponse("ok")

        self.vista_cliente = vista_cliente
        self.vista_admin = vista_admin

    def _pedir(self, vista, usuario):
        request = self.rf.get("/x/")
        request.user = usuario
        return vista(request)

    def test_visitante_va_al_login(self):
        for vista in (self.vista_cliente, self.vista_admin):
            resp = self._pedir(vista, AnonymousUser())
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/cuentas/login/", resp.url)

    def test_cliente_puede_en_vista_de_cliente_pero_no_en_admin(self):
        self.assertEqual(self._pedir(self.vista_cliente, self.cliente).status_code, 200)
        with self.assertRaises(PermissionDenied):
            self._pedir(self.vista_admin, self.cliente)

    def test_admin_puede_en_vista_de_admin_pero_no_en_cliente(self):
        self.assertEqual(self._pedir(self.vista_admin, self.admin).status_code, 200)
        with self.assertRaises(PermissionDenied):
            self._pedir(self.vista_cliente, self.admin)
