from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogo.models import Categoria, MovimientoStock, Producto
from catalogo.servicios import StockInsuficiente, ajustar_stock
from cuentas.decorators import administrador_requerido
from pedidos.models import Pedido
from pedidos.servicios import PedidoInvalido, cambiar_estado, estados_siguientes

from .forms import AjusteStockForm, CategoriaForm, ProductoForm


def _paginar(request, queryset, por_pagina):
    pagina = Paginator(queryset, por_pagina).get_page(request.GET.get("page"))
    parametros = request.GET.copy()
    parametros.pop("page", None)
    return pagina, parametros.urlencode()


@administrador_requerido
def inicio(request):
    return redirect("panel_productos")


# ---------------- Productos ----------------

@administrador_requerido
def productos(request):
    consulta = Producto.objects.select_related("categoria").order_by("nombre", "talla")
    q = request.GET.get("q", "").strip()
    if q:
        consulta = consulta.filter(nombre__icontains=q)
    pagina, querystring = _paginar(request, consulta, 10)
    return render(
        request, "panel/productos.html",
        {"seccion": "productos", "pagina": pagina, "q": q, "querystring": querystring},
    )


@administrador_requerido
def producto_nuevo(request):
    form = ProductoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            producto = form.save()
            stock_inicial = form.cleaned_data.get("stock_inicial") or 0
            if stock_inicial > 0:
                ajustar_stock(
                    producto.pk, stock_inicial, MovimientoStock.Tipo.ENTRADA,
                    request.user, motivo="Stock inicial",
                )
        messages.success(request, f"Producto «{producto.nombre}» creado.")
        return redirect("panel_productos")
    return render(
        request, "panel/formulario.html",
        {"seccion": "productos", "titulo": "Nuevo producto", "form": form,
         "multipart": True, "volver": "panel_productos"},
    )


@administrador_requerido
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Producto «{producto.nombre}» actualizado.")
        return redirect("panel_productos")
    return render(
        request, "panel/formulario.html",
        {"seccion": "productos", "titulo": f"Editar: {producto.nombre}", "form": form,
         "multipart": True, "volver": "panel_productos",
         "info": f"Stock actual: {producto.stock}. Para cambiarlo usa «Ajustar stock»."},
    )


@administrador_requerido
@require_POST
def producto_toggle(request, pk):
    """Activar / desactivar: un producto desactivado se oculta del catálogo
    pero conserva su historial de pedidos y de stock."""
    producto = get_object_or_404(Producto, pk=pk)
    producto.activo = not producto.activo
    producto.save(update_fields=["activo"])
    estado = "activado" if producto.activo else "desactivado"
    messages.success(request, f"Producto «{producto.nombre}» {estado}.")
    return redirect(request.POST.get("volver") or "panel_productos")


@administrador_requerido
def producto_stock(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    form = AjusteStockForm(request.POST or None, producto=producto)
    if request.method == "POST" and form.is_valid():
        datos = form.cleaned_data
        try:
            movimiento = ajustar_stock(
                producto.pk, datos["cantidad"], datos["tipo"], request.user, datos["motivo"]
            )
        except StockInsuficiente as error:
            form.add_error(None, str(error))
        else:
            messages.success(
                request,
                f"Stock de «{producto.nombre}»: de {movimiento.stock_anterior} a {movimiento.stock_nuevo}.",
            )
            return redirect("panel_productos")
    return render(
        request, "panel/formulario.html",
        {"seccion": "productos", "titulo": f"Ajustar stock: {producto.nombre} ({producto.talla})",
         "form": form, "volver": "panel_productos",
         "info": f"Stock actual: {producto.stock}. Cada cambio queda registrado en el historial."},
    )


# ---------------- Categorías ----------------

@administrador_requerido
def categorias(request):
    lista = Categoria.objects.annotate(num_productos=Count("productos"))
    return render(request, "panel/categorias.html", {"seccion": "categorias", "categorias": lista})


@administrador_requerido
def categoria_nueva(request):
    form = CategoriaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        categoria = form.save()
        messages.success(request, f"Categoría «{categoria.nombre}» creada.")
        return redirect("panel_categorias")
    return render(
        request, "panel/formulario.html",
        {"seccion": "categorias", "titulo": "Nueva categoría", "form": form,
         "volver": "panel_categorias"},
    )


@administrador_requerido
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    form = CategoriaForm(request.POST or None, instance=categoria)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Categoría «{categoria.nombre}» actualizada.")
        return redirect("panel_categorias")
    return render(
        request, "panel/formulario.html",
        {"seccion": "categorias", "titulo": f"Editar: {categoria.nombre}", "form": form,
         "volver": "panel_categorias"},
    )


@administrador_requerido
@require_POST
def categoria_eliminar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    try:
        categoria.delete()
        messages.success(request, f"Categoría «{categoria.nombre}» eliminada.")
    except ProtectedError:
        messages.error(
            request,
            f"No se puede eliminar «{categoria.nombre}» porque tiene productos asociados.",
        )
    return redirect("panel_categorias")


# ---------------- Pedidos ----------------

@administrador_requerido
def pedidos(request):
    consulta = Pedido.objects.select_related("usuario")
    estado = request.GET.get("estado", "")
    if estado in Pedido.Estado.values:
        consulta = consulta.filter(estado=estado)
    else:
        estado = ""
    pagina, querystring = _paginar(request, consulta, 10)
    pagina.object_list = list(pagina.object_list)
    for pedido in pagina.object_list:
        pedido.siguientes = estados_siguientes(pedido)
    return render(
        request, "panel/pedidos.html",
        {"seccion": "pedidos", "pagina": pagina, "estado": estado,
         "estados": Pedido.Estado.choices, "querystring": querystring},
    )


@administrador_requerido
def pedido_detalle(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.select_related("usuario").prefetch_related("detalles__producto"), pk=pk
    )
    pedido.siguientes = estados_siguientes(pedido)
    movimientos = pedido.movimientos_stock.select_related("producto", "usuario")
    return render(
        request, "panel/pedido_detalle.html",
        {"seccion": "pedidos", "pedido": pedido, "movimientos": movimientos},
    )


@administrador_requerido
@require_POST
def pedido_estado(request, pk):
    get_object_or_404(Pedido, pk=pk)
    try:
        pedido = cambiar_estado(pk, request.POST.get("estado", ""), request.user)
        messages.success(request, f"Pedido #{pedido.pk}: estado «{pedido.get_estado_display()}».")
    except PedidoInvalido as error:
        messages.error(request, str(error))
    if request.POST.get("volver") == "detalle":
        return redirect("panel_pedido_detalle", pk=pk)
    return redirect("panel_pedidos")


# ---------------- Historial de stock ----------------

@administrador_requerido
def historial(request):
    movimientos = MovimientoStock.objects.select_related("producto", "usuario", "pedido")

    producto_id = request.GET.get("producto", "")
    if producto_id.isdigit():
        movimientos = movimientos.filter(producto_id=int(producto_id))
    else:
        producto_id = ""

    tipo = request.GET.get("tipo", "")
    if tipo in MovimientoStock.Tipo.values:
        movimientos = movimientos.filter(tipo=tipo)
    else:
        tipo = ""

    # Auditoría: el stock de cada producto debe ser igual a la suma de sus movimientos
    inconsistentes = [
        p
        for p in Producto.objects.annotate(suma=Coalesce(Sum("movimientos__cantidad"), 0))
        if p.suma != p.stock
    ]

    pagina, querystring = _paginar(request, movimientos, 20)
    return render(
        request, "panel/historial.html",
        {"seccion": "historial", "pagina": pagina, "querystring": querystring,
         "productos": Producto.objects.order_by("nombre", "talla"),
         "tipos": MovimientoStock.Tipo.choices,
         "producto_id": producto_id, "tipo": tipo, "inconsistentes": inconsistentes},
    )
