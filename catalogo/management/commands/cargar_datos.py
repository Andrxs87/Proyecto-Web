"""Carga usuarios, categorías y productos de prueba.

Uso:  python manage.py cargar_datos
Se puede ejecutar varias veces sin duplicar datos.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from catalogo.models import Categoria, MovimientoStock, Producto
from catalogo.servicios import ajustar_stock
from pedidos.models import Carrito, ItemCarrito, Pedido
from pedidos.servicios import cambiar_estado, crear_pedido

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
    # Mismo producto en otras tallas (una fila por talla)
    ("Camisetas", "Camiseta oversize", "Algodón 100%, corte holgado", 89900, "S", 10),
    ("Camisetas", "Camiseta oversize", "Algodón 100%, corte holgado", 89900, "L", 4),
    ("Pantalones", "Jean recto", "Denim azul medio", 129900, "L", 0),
    ("Accesorios", "Bufanda tejida", "Lana suave", 59900, "UNICA", 9),
    ("Chaquetas", "Buzo con capota", "Algodón perchado", 139900, "XL", 6),
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

        cliente2, creado = Usuario.objects.get_or_create(
            username="cliente2",
            defaults={"email": "cliente2@correo.com", "first_name": "Camila",
                      "last_name": "Ruiz", "direccion": "Carrera 27 # 45-10, Bucaramanga"},
        )
        if creado:
            cliente2.set_password("Cliente12345!")
            cliente2.save()

        for cat, nombre, desc, precio, talla, stock in PRODUCTOS:
            categoria, _ = Categoria.objects.get_or_create(nombre=cat)
            producto, creado = Producto.objects.get_or_create(
                nombre=nombre, talla=talla,
                defaults={"categoria": categoria, "descripcion": desc, "precio": precio},
            )
            # El stock inicial también se registra en el historial
            if creado and stock > 0:
                ajustar_stock(producto.pk, stock, MovimientoStock.Tipo.ENTRADA,
                              admin, motivo="Stock inicial")

        if not Pedido.objects.exists():
            self.crear_pedidos_demo(admin, cliente, cliente2)

        self.stdout.write(self.style.SUCCESS("Datos de prueba cargados."))
        self.stdout.write("Admin:   admin / Admin12345!")
        self.stdout.write("Cliente: cliente1 / Cliente12345!  (también cliente2)")

    def crear_pedidos_demo(self, admin, cliente1, cliente2):
        """Pedidos de ejemplo en distintos estados, creados con los mismos
        servicios que usa la aplicación (así el stock y el historial cuadran)."""
        demos = [
            # (cliente, [(nombre, talla, cantidad)], dirección, estados por los que pasa)
            (cliente1, [("Camiseta oversize", "M", 2), ("Jean recto", "M", 1)], []),
            (cliente1, [("Chaqueta bomber", "M", 1)], ["enviado"]),
            (cliente2, [("Polo clásico", "S", 2), ("Gorra negra", "UNICA", 1)], ["enviado", "entregado"]),
            (cliente2, [("Pantalón cargo", "M", 1)], ["cancelado"]),
        ]
        for usuario, items, estados in demos:
            carrito, _ = Carrito.objects.get_or_create(usuario=usuario)
            for nombre, talla, cantidad in items:
                producto = Producto.objects.get(nombre=nombre, talla=talla)
                ItemCarrito.objects.create(carrito=carrito, producto=producto, cantidad=cantidad)
            pedido = crear_pedido(usuario, usuario.direccion)
            for estado in estados:
                cambiar_estado(pedido.pk, estado, admin)
