// Catálogo: actualiza los resultados con fetch, sin recargar la página.
// Si JavaScript falla o está desactivado, el formulario funciona igual (GET normal).
document.addEventListener("DOMContentLoaded", () => {
    const formulario = document.getElementById("form-filtros");
    const resultados = document.getElementById("resultados");
    if (!formulario || !resultados) return;

    let temporizador;

    async function cargar(url) {
        try {
            const respuesta = await fetch(url, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!respuesta.ok) throw new Error("Error " + respuesta.status);
            resultados.innerHTML = await respuesta.text();
            history.replaceState(null, "", url); // la URL queda compartible
        } catch (error) {
            console.error("No se pudo actualizar el catálogo:", error);
            window.location.href = url; // plan B: carga normal
        }
    }

    function urlConFiltros() {
        const parametros = new URLSearchParams(new FormData(formulario));
        return `${formulario.action}?${parametros}`;
    }

    // Al escribir o cambiar un filtro, espera 300 ms y busca
    formulario.addEventListener("input", () => {
        clearTimeout(temporizador);
        temporizador = setTimeout(() => cargar(urlConFiltros()), 300);
    });

    formulario.addEventListener("submit", (evento) => {
        evento.preventDefault();
        cargar(urlConFiltros());
    });

    // Paginación sin recargar
    resultados.addEventListener("click", (evento) => {
        const enlace = evento.target.closest("a.pagina");
        if (!enlace) return;
        evento.preventDefault();
        cargar(enlace.href);
    });
});
