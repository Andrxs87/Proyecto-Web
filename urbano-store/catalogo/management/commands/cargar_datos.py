"""Carga usuarios, categorías y productos de prueba.

Uso:  python manage.py cargar_datos
Se puede ejecutar varias veces sin duplicar datos.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from catalogo.models import Categoria, MovimientoStock, Producto
from catalogo.servicios import ajustar_stock

PRODUCTOS = [
    # (categoría, nombre, descripción, precio, talla, stock inicial)
    ("Camisetas", "Camiseta oversize", "Algodón 100%, corte holgado", 89900, "M", 12),
    ("Camisetas", "Camiseta básica blanca", "Algodón peinado", 49900, "L", 20),
    ("Camisetas", "Polo clásico", "Piqué con cuello tejido", 74900, "S", 15),
    ("Pantalones", "Jean recto", "Denim azul medio", 129900, "M", 8),
    ("Pantalones", "Jogger gris", "Felpa suave con puño", 99900, "L", 10),
    ("Pantalones", "Pantalón cargo", "Seis bolsillos", 119900, "M", 6),
    ("Chaquetas", "Chaqueta bomber", "Forro interno ligero", 189900, "M", 5),
    ("Chaquetas", "Chaqueta jean", "Denim con botones metálicos", 159900, "L", 7),
    ("Accesorios", "Gorra negra", "Ajustable", 39900, "UNICA", 25),
]


class Command(BaseCommand):
    help = "Carga datos de prueba (usuarios, categorías y productos)."

    def handle(self, *args, **options):
        Usuario = get_user_model()

        admin, creado = Usuario.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@urbanostore.co", "first_name": "Admin",
                      "last_name": "Urbano", "is_staff": True, "is_superuser": True},
        )
        if creado:
            admin.set_password("Admin12345!")
            admin.save()

        cliente, creado = Usuario.objects.get_or_create(
            username="cliente1",
            defaults={"email": "cliente1@correo.com", "first_name": "Laura",
                      "last_name": "Gómez", "direccion": "Calle 10 # 5-20, Bucaramanga"},
        )
        if creado:
            cliente.set_password("Cliente12345!")
            cliente.save()

        for cat, nombre, desc, precio, talla, stock in PRODUCTOS:
            categoria, _ = Categoria.objects.get_or_create(nombre=cat)
            producto, creado = Producto.objects.get_or_create(
                nombre=nombre, talla=talla,
                defaults={"categoria": categoria, "descripcion": desc, "precio": precio},
            )
            # El stock inicial también se registra en el historial
            if creado:
                ajustar_stock(producto.pk, stock, MovimientoStock.Tipo.ENTRADA,
                              admin, motivo="Stock inicial")

        self.stdout.write(self.style.SUCCESS("Datos de prueba cargados."))
        self.stdout.write("Admin:   admin / Admin12345!")
        self.stdout.write("Cliente: cliente1 / Cliente12345!")
