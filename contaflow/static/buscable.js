/*
 * Convierte cualquier <select class="buscable"> en un campo de texto con
 * autocompletado (vía <datalist>, sin librerías externas), para no tener que
 * desplazarse por listas largas — el plan de cuentas completo, por ejemplo.
 *
 * El <select> original NO se quita del DOM: sólo se oculta. Sigue mandando
 * su valor con el formulario exactamente igual que antes, así que no hace
 * falta tocar ninguna ruta del servidor — sólo agregar la clase "buscable"
 * al <select> que se quiera mejorar.
 */
(function () {
  "use strict";

  function mejorar(select) {
    if (select.dataset.buscableListo) return;
    select.dataset.buscableListo = "1";

    const opciones = Array.from(select.options);
    const id = "dl-" + Math.random().toString(36).slice(2);

    const datalist = document.createElement("datalist");
    datalist.id = id;
    opciones.forEach(function (opt) {
      if (!opt.value) return; // se salta "— Seleccionar —"
      const o = document.createElement("option");
      o.value = opt.textContent;
      datalist.appendChild(o);
    });

    const input = document.createElement("input");
    input.type = "text";
    input.setAttribute("list", id);
    input.setAttribute("autocomplete", "off");
    input.placeholder = select.dataset.placeholder || "Escribe para buscar…";
    input.className = select.className;
    const actual = opciones.find(function (o) { return o.value === select.value; });
    input.value = actual && actual.value ? actual.textContent : "";

    input.addEventListener("input", function () {
      const coincidencia = opciones.find(function (o) { return o.textContent === input.value; });
      if (coincidencia) {
        select.value = coincidencia.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        select.value = "";
      }
    });

    select.insertAdjacentElement("afterend", input);
    select.insertAdjacentElement("afterend", datalist);
    select.style.display = "none";
    select.setAttribute("aria-hidden", "true");
  }

  function mejorarTodos(raiz) {
    (raiz || document).querySelectorAll("select.buscable").forEach(mejorar);
  }

  document.addEventListener("DOMContentLoaded", function () {
    mejorarTodos(document);
  });

  // Para filas agregadas después de cargar la página (una línea nueva de
  // asiento, por ejemplo): se llama de nuevo tras insertar el <select> en
  // el DOM. mejorar() ya se salta los que estén marcados como listos.
  window.mejorarBuscables = mejorarTodos;
})();
