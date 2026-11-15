from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuario del sistema.

    Roles:
    - Visitante: no inició sesión (no se guarda en la BD).
    - Cliente: usuario autenticado con is_staff = False.
    - Administrador: usuario autenticado con is_staff = True.
    """

    email = models.EmailField("correo electrónico", unique=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=200, blank=True)

    @property
    def es_administrador(self):
        return self.is_staff

    def __str__(self):
        return self.get_full_name() or self.username
