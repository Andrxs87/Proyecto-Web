// Detalle de producto: agrega al carrito con fetch, sin recargar la página.
// Si JavaScript falla o está desactivado, el formulario funciona igual (POST normal).
document.addEventListener("DOMContentLoaded", () => {
    const formulario = document.getElementById("form-agregar");
    const mensaje = document.getElementById("mensaje-carrito");
    const contador = document.getElementById("carrito-contador");
    if (!formulario || !mensaje) return;

    formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        const boton = formulario.querySelector("button[type=submit]");
        boton.disabled = true;

        try {
            // El token CSRF viaja dentro del FormData
            const respuesta = await fetch(formulario.action, {
                method: "POST",
                body: new FormData(formulario),
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const datos = await respuesta.json();

            mensaje.textContent = datos.mensaje;
            mensaje.className = datos.ok ? "mensaje-ok" : "mensaje-error";
            if (datos.ok && contador) contador.textContent = datos.items;
        } catch (error) {
            console.error("No se pudo agregar al carrito:", error);
            formulario.submit(); // plan B: envío normal del formulario
            return;
        }
        boton.disabled = false;
    });
});
