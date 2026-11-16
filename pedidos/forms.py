from django import forms


class DireccionEnvioForm(forms.Form):
    direccion_envio = forms.CharField(
        label="Dirección de envío",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Calle, número, barrio y ciudad"}),
    )
