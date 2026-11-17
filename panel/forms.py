from django import forms

from catalogo.models import Categoria, MovimientoStock, Producto


class ProductoForm(forms.ModelForm):
    """Crear / editar producto. El stock NO se edita aquí (solo en 'Ajustar stock')."""

    stock_inicial = forms.IntegerField(
        label="Stock inicial",
        min_value=0,
        initial=0,
        required=False,
        help_text="Solo se pide al crear. Después, el stock se cambia desde «Ajustar stock».",
    )

    class Meta:
        model = Producto
        fields = ["categoria", "nombre", "descripcion", "precio", "talla", "imagen", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            del self.fields["stock_inicial"]


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion"]


class AjusteStockForm(forms.Form):
    tipo = forms.ChoiceField(
        label="Tipo de movimiento",
        choices=[
            (MovimientoStock.Tipo.ENTRADA, "Entrada (reposición de mercancía)"),
            (MovimientoStock.Tipo.AJUSTE, "Ajuste (corrección de inventario)"),
        ],
    )
    cantidad = forms.IntegerField(
        label="Cantidad",
        help_text="En un ajuste puede ser negativa (por ejemplo -2 si faltan 2 unidades).",
    )
    motivo = forms.CharField(
        label="Motivo", max_length=255, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Obligatorio en los ajustes"}),
    )

    def __init__(self, *args, producto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.producto = producto

    def clean(self):
        datos = super().clean()
        tipo, cantidad = datos.get("tipo"), datos.get("cantidad")
        motivo = (datos.get("motivo") or "").strip()
        if tipo is None or cantidad is None:
            return datos

        if cantidad == 0:
            self.add_error("cantidad", "La cantidad no puede ser cero.")
        elif tipo == MovimientoStock.Tipo.ENTRADA and cantidad < 0:
            self.add_error("cantidad", "Una entrada debe ser positiva. Para restar usa un ajuste.")
        elif tipo == MovimientoStock.Tipo.AJUSTE and not motivo:
            self.add_error("motivo", "El motivo es obligatorio en un ajuste.")
        elif self.producto and self.producto.stock + cantidad < 0:
            self.add_error(
                "cantidad",
                f"El stock no puede quedar negativo (stock actual: {self.producto.stock}).",
            )
        datos["motivo"] = motivo
        return datos
