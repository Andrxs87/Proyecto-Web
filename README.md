# Urbano Store

Tienda de ropa en línea desarrollada con **Django**

Los clientes exploran un catálogo, arman un carrito y realizan pedidos; un administrador
gestiona productos, categorías y pedidos, con un **historial auditable del inventario**.

## Integrantes

| Código | Nombre |
|---|---|
| 2242034 | Andres Felipe Guaqueta Rojas |
| 2242029 | Maria Jose De Moya Gomez |

## Funcionalidades por rol

| Rol | Qué puede hacer |
|---|---|
| **Visitante** | Ver el catálogo (filtros, búsqueda, orden y paginación), ver el detalle de un producto, registrarse e iniciar sesión |
| **Cliente** | Todo lo anterior, más: manejar su carrito (agregar, cambiar cantidad, quitar), finalizar pedidos, ver su historial de pedidos y cancelar pedidos pendientes |
| **Administrador** | Crear, editar y desactivar productos y categorías; registrar entradas y ajustes de stock; ver todos los pedidos y cambiar su estado; consultar el historial de stock |

Fuera del alcance: pagos reales, cálculo de envíos, devoluciones, reseñas, recomendaciones y
notificaciones por correo.

## Arquitectura y tecnologías

Arquitectura **híbrida**: aplicación multipágina (MPA) renderizada en el servidor con Django, más
JavaScript (`fetch`) en interacciones puntuales (agregar al carrito y filtrar el catálogo sin
recargar la página). Si JavaScript falla, todo sigue funcionando con recarga normal.

- **Backend:** Python 3 y Django 5.2
- **Frontend:** plantillas de Django (DTL), HTML5 semántico, CSS y JavaScript
- **Base de datos:** SQLite
- **Imágenes:** Pillow
- **Control de versiones:** Git y GitHub

### Apps del proyecto

| App | Responsabilidad |
|---|---|
| `cuentas` | Usuario personalizado, registro, login, logout y decoradores de roles |
| `catalogo` | Categorías, productos, historial de stock y página de inicio |
| `pedidos` | Carrito, pedidos y su ciclo de vida |
| `panel` | Panel del administrador |

## Inventario auditable

El stock de un producto **nunca se modifica directamente**: solo cambia mediante
`catalogo.servicios.ajustar_stock()`, que dentro de una transacción actualiza el stock y registra un
`MovimientoStock` (quién, cuándo, cuánto, por qué y cómo quedó). El historial no se puede editar ni
borrar, y el panel verifica que el stock de cada producto coincida con la suma de sus movimientos.

Los pedidos también son transaccionales: si un producto no tiene stock suficiente, no se guarda nada.

## Instalación y ejecución

Requiere **Python 3.10 o superior**.

```bash
# 1. Clonar el repositorio y entrar a la carpeta
git clone <URL-del-repositorio>
cd <carpeta-del-repositorio>

# 2. Crear y activar el entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear la base de datos y cargar datos de prueba
python manage.py migrate
python manage.py cargar_datos

# 5. Iniciar el servidor
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/>.

## Usuarios de prueba

`python manage.py cargar_datos` crea (se puede ejecutar varias veces sin duplicar datos):

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `Admin12345!` |
| Cliente | `cliente1` | `Cliente12345!` |
| Cliente | `cliente2` | `Cliente12345!` |

También crea 14 productos con su stock inicial y 4 pedidos de ejemplo (pendiente, enviado,
entregado y cancelado). El panel del administrador está en `/panel/`.


## Pruebas automáticas

```bash
python manage.py test
```
