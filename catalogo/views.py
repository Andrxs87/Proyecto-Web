from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .forms import FiltroProductosForm
from .models import Categoria, Producto

PRODUCTOS_POR_PAGINA = 6
ORDEN_SQL = {
    "novedad": "-fecha_creacion",
    "precio_asc": "precio",
    "precio_desc": "-precio",
}


def inicio(request):
    contexto = {
        "categorias": Categoria.objects.all(),
        "destacados": Producto.objects.filter(activo=True).select_related("categoria")[:4],
    }
    return render(request, "inicio.html", contexto)


def lista_productos(request):
    # Solo se muestran productos activos (los desactivados quedan ocultos)
    productos = Producto.objects.filter(activo=True).select_related("categoria")

    form = FiltroProductosForm(request.GET)
    orden = "novedad"
    if form.is_valid():
        datos = form.cleaned_data
        if datos["q"]:
            productos = productos.filter(
                Q(nombre__icontains=datos["q"]) | Q(descripcion__icontains=datos["q"])
            )
        if datos["categoria"]:
            productos = productos.filter(categoria=datos["categoria"])
        if datos["talla"]:
            productos = productos.filter(talla=datos["talla"])
        if datos["precio_min"] is not None:
            productos = productos.filter(precio__gte=datos["precio_min"])
        if datos["precio_max"] is not None:
            productos = productos.filter(precio__lte=datos["precio_max"])
        orden = datos["orden"] or "novedad"

    productos = productos.order_by(ORDEN_SQL[orden], "-id")

    paginador = Paginator(productos, PRODUCTOS_POR_PAGINA)
    pagina = paginador.get_page(request.GET.get("page"))

    # Querystring sin "page", para que los enlaces de paginación conserven los filtros
    parametros = request.GET.copy()
    parametros.pop("page", None)

    contexto = {
        "form": form,
        "pagina": pagina,
        "total": paginador.count,
        "querystring": parametros.urlencode(),
    }

    # Si la petición viene de fetch (JavaScript), se devuelve solo el fragmento
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "catalogo/_resultados.html", contexto)
    return render(request, "catalogo/lista.html", contexto)


def detalle_producto(request, pk):
    producto = get_object_or_404(
        Producto.objects.select_related("categoria"), pk=pk, activo=True
    )
    # Mismo producto en otras tallas (se modela repitiendo el producto por talla)
    otras_tallas = (
        Producto.objects.filter(activo=True, nombre=producto.nombre, categoria=producto.categoria)
        .exclude(pk=producto.pk)
        .order_by("talla")
    )
    return render(
        request, "catalogo/detalle.html",
        {"producto": producto, "otras_tallas": otras_tallas},
    )
