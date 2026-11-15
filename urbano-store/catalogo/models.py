from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    class Talla(models.TextChoices):
        XS = "XS", "XS"
        S = "S", "S"
        M = "M", "M"
        L = "L", "L"
        XL = "XL", "XL"
        XXL = "XXL", "XXL"
        UNICA = "UNICA", "Única"

    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="productos"
    )
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    talla = models.CharField(max_length=5, choices=Talla.choices, default=Talla.M)
    # editable=False: el stock NO se puede editar desde formularios ni desde
    # el panel. Solo cambia con catalogo.servicios.ajustar_stock(), que deja
    # registro en MovimientoStock.
    stock = models.PositiveIntegerField(default=0, editable=False)
    imagen = models.ImageField(upload_to="productos/", blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.nombre} ({self.talla})"


class MovimientoStock(models.Model):
    """Historial (kardex) de cambios de stock. Solo se inserta, nunca se edita."""

    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        VENTA = "venta", "Venta"
        CANCELACION = "cancelacion", "Cancelación"
        AJUSTE = "ajuste", "Ajuste"

    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="movimientos"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimientos_stock",
    )
    pedido = models.ForeignKey(
        "pedidos.Pedido",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_stock",
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    cantidad = models.IntegerField()  # con signo: + suma, - resta
    stock_anterior = models.PositiveIntegerField()
    stock_nuevo = models.PositiveIntegerField()
    motivo = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "movimiento de stock"
        verbose_name_plural = "movimientos de stock"
        ordering = ["-fecha", "-id"]
        indexes = [models.Index(fields=["producto", "fecha"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(stock_nuevo=F("stock_anterior") + F("cantidad")),
                name="chk_mov_calculo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(tipo__in=["entrada", "cancelacion"], cantidad__gt=0)
                    | Q(tipo="venta", cantidad__lt=0)
                    | Q(tipo="ajuste", cantidad__lt=0)
                    | Q(tipo="ajuste", cantidad__gt=0)
                ),
                name="chk_mov_signo",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionDenied("El historial de stock no se puede modificar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("El historial de stock no se puede eliminar.")

    def __str__(self):
        return f"{self.producto} | {self.tipo} {self.cantidad:+d}"
