from django import forms

from .models import Categoria, Producto

ORDENES = [
    ("novedad", "Novedades"),
    ("precio_asc", "Precio: menor a mayor"),
    ("precio_desc", "Precio: mayor a menor"),
]


class FiltroProductosForm(forms.Form):
    """Filtros del catálogo (se envían por GET, así se pueden compartir por URL)."""

    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={"placeholder": "Buscar prendas..."}),
    )
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(),
        required=False,
        empty_label="Todas",
        label="Categoría",
    )
    talla = forms.ChoiceField(
        required=False,
        choices=[("", "Todas")] + Producto.Talla.choices,
        label="Talla",
    )
    precio_min = forms.DecimalField(
        required=False, min_value=0, label="Precio mínimo",
        widget=forms.NumberInput(attrs={"placeholder": "Mín."}),
    )
    precio_max = forms.DecimalField(
        required=False, min_value=0, label="Precio máximo",
        widget=forms.NumberInput(attrs={"placeholder": "Máx."}),
    )
    orden = forms.ChoiceField(required=False, choices=ORDENES, label="Ordenar por")
