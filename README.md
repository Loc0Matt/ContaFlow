# ContaFlow — Sistema Contable Chileno Multiempresa

> Creado por **Loc0Matt** · 2026 · Código abierto bajo licencia [MIT](LICENSE)

Sistema contable completo para llevar una cartera pequeña de clientes, construido según
la normativa chilena. Funciona **100% offline** en tu computador Windows: no se conecta
al SII ni a ningún servicio externo, y todos los datos viven en un solo archivo en tu disco.

Genera **propuestas de formularios** (F29 mensual y F22 anual) con los códigos calculados
desde tu propia contabilidad, para que los uses como base al llenar los formularios
oficiales del SII.

---

## Descargar el ejecutable

El `.exe` se construye automáticamente en un runner de Windows cada vez que se
actualiza el repositorio.

1. Entra a la pestaña **Actions** del repositorio en GitHub.
2. Abre la ejecución más reciente de **«Construir ContaFlow.exe (Windows)»**.
3. En la sección *Artifacts*, descarga **ContaFlow-Windows**.
4. Descomprime el ZIP: dentro está `ContaFlow.exe`.

Colócalo donde quieras (Escritorio, `C:\ContaFlow\`, un pendrive) y ábrelo con doble clic.
**No necesitas instalar Python ni nada más.**

En el mismo ZIP viene **`Manual-ContaFlow.pdf`**: 48 páginas con índice clickeable que
explican cada apartado del sistema y las 145 cuentas del plan contable, una por una.

> Windows SmartScreen puede advertir porque el ejecutable no está firmado digitalmente.
> Elige **Más información → Ejecutar de todas formas**. Ocurre con cualquier programa
> sin certificado de firma comercial.

### Construirlo tú mismo en Windows

Si prefieres compilarlo en tu propio equipo:

1. Instala [Python 3.11+](https://www.python.org/downloads/) marcando **«Add Python to PATH»**.
2. Descarga el repositorio como ZIP y descomprímelo.
3. Doble clic en **`build\construir_exe.bat`**.

El script crea el entorno, instala dependencias, corre las pruebas y deja el ejecutable
en `dist\ContaFlow.exe`.

---

## Documentación

| Documento | Qué contiene |
|---|---|
| **[`docs/Manual-ContaFlow.pdf`](docs/Manual-ContaFlow.pdf)** | Manual completo de 48 páginas para un usuario nuevo: índice clickeable, marcadores en el lector, referencias cruzadas y un **diccionario con las 145 cuentas del plan** — qué registra cada una, cuándo se carga y cuándo se abona. |
| [`docs/manual.md`](docs/manual.md) | La misma guía en texto plano, para leer en GitHub. |

El PDF se regenera con:

```bash
python herramientas/generar_manual.py
```

## Poner tu logotipo

Deja tu imagen en **`contaflow/static/logo.png`** (también sirve `.jpg` o `.svg`).
Con eso basta: la aplicación la usa automáticamente en la barra lateral, la pantalla
de ingreso, el favicon, la portada del manual y el icono del `.exe`.

Desde GitHub, sin instalar nada: entra a la carpeta `contaflow/static`, pulsa
**Add file → Upload files**, arrastra tu imagen renombrada como `logo.png` y confirma.
La siguiente compilación toma el logo sola.

Recomendado: PNG cuadrado con fondo transparente, 512×512 px o más. Mientras no haya
uno propio se usa el escudo de reserva `logo-generico.svg`.

## Primer uso

1. Abre `ContaFlow.exe`. Se abre **en su propia ventana de escritorio**, sin
   navegador a la vista.
2. Ingresa con **usuario `admin`, contraseña `admin`**.
3. Cámbiala en *Configuración → Respaldos*.
4. Crea tu primera empresa en *Empresas → Nueva empresa*. Al guardar se genera
   automáticamente el **plan de cuentas chileno completo** (más de 140 cuentas).
5. Carga la **UF, UTM e ingreso mínimo** del año en *Maestros → Indicadores*
   (sólo necesario si vas a emitir liquidaciones de sueldo).

Para cerrar el sistema, cierra la ventana.

### Cómo funciona por dentro

ContaFlow es una aplicación de escritorio, pero su interfaz está hecha con tecnología
web y la dibuja un pequeño servidor que corre **dentro de tu propio computador**. Por eso
existe la dirección `http://127.0.0.1:8777`: es el programa hablando consigo mismo, no
internet. Nadie más puede acceder.

La ventana usa **WebView2**, el motor que Windows 10 y 11 ya traen instalado. Si en tu
equipo faltara, el sistema abre el navegador en «modo aplicación» (una ventana limpia,
sin barra de direcciones ni pestañas) y, como último recurso, el navegador normal con
una ventanita para cerrar el servidor. En cualquiera de los tres casos el programa
funciona igual.

### Dónde quedan tus datos

Todo se guarda en:

```
C:\Users\<tu usuario>\AppData\Local\ContaFlow\contaflow.db
```

Ese único archivo contiene **todas** las empresas. Respáldalo desde
*Configuración → Respaldos* o cópialo a mano. Si actualizas el `.exe`, los datos se
conservan porque viven fuera del ejecutable.

### Actualizar ContaFlow

No hay actualización automática por internet (el sistema es offline a propósito).
Actualizar es descargar el `.exe` nuevo y reemplazar el viejo — nada más. Como los
datos viven aparte (ver arriba), reemplazar el ejecutable no los toca.

Si una actualización necesita cambiar la estructura de la base de datos (agregar un
campo nuevo a una tabla existente, por ejemplo), ContaFlow lo detecta y lo aplica solo
al abrir, y crea automáticamente un respaldo completo justo antes de tocar nada — no
hace falta hacer nada manual ni acordarse de nada. Puedes ver la versión de esquema
aplicada en *Configuración → Respaldos*.

El `.exe` anterior no se borra solo: si quieres conservarlo como respaldo, simplemente
no lo sobrescribas (guárdalo con otro nombre). Ambas versiones leen la misma carpeta
de datos.

---

## Qué incluye

### Multiempresa
Empresas ilimitadas, cada una con su propio plan de cuentas, libros, documentos,
trabajadores y declaraciones. Cambias entre ellas desde el selector superior.
Se registra RUT, giro, código de actividad, representante legal, régimen tributario
(14 A, 14 D N°3, 14 D N°8, Renta Presunta, Segunda Categoría) y tasa de PPM.

### Contabilidad
- **Plan de cuentas chileno** precargado, jerárquico y editable. Marca cuentas como
  imputables, con auxiliar obligatorio, con centro de costo o bancarias.
- **Comprobantes** de ingreso, egreso, traspaso, apertura, cierre y ajuste, con
  numeración correlativa por tipo y año. **No se guarda un asiento descuadrado**:
  el formulario valida en vivo y el servidor lo rechaza.
- **Libro Diario**, **Libro Mayor** con saldo corrido y **Balance de Comprobación y
  Saldos de 8 columnas**.
- **Centros de costo** para repartir ingresos y gastos.
- **Conciliación bancaria** marcando movimientos contra la cartola.
- **Cierre de períodos** mensual (bloquea meses ya declarados) y **asiento de cierre
  de ejercicio** que traspasa las cuentas de resultado.

### Tributario
- **Libros de Compras y Ventas** con el catálogo oficial de tipos de DTE del SII
  (33, 34, 39, 41, 46, 52, 56, 61, 110, 914…).
- Cálculo automático de IVA al 19%, con modo «ingreso el neto» (facturas) o
  «ingreso el total con IVA incluido» (boletas).
- Exento, impuestos adicionales (ILA), IVA no recuperable, IVA de uso común,
  retenciones por cambio de sujeto y referencias para notas de crédito/débito.
- Clasificación del registro de compras: del giro, activo fijo, supermercado,
  uso común, sin derecho a crédito.
- **Centralización contable automática**: cada documento genera su asiento cuadrado.
  Las notas de crédito invierten el asiento automáticamente.
- **Boletas de honorarios** recibidas y emitidas, con la tabla de retención de la
  Ley 21.133 por año (14,5% en 2025, 15,25% en 2026…).
- Exportación de los libros en **CSV con el formato de columnas del SII**, Excel
  (con hoja de resumen por tipo de documento) y PDF.

### Formularios
- **Formulario 29** — propuesta mensual con los códigos calculados desde tus libros:
  débitos (110, 111, 502, 503, 509, 510, 512, 513, 142, 585), créditos (519, 520,
  524, 525, 527, 528, 531, 532, 534, 535, 553, 554), determinación del IVA (504, 89, 77),
  retenciones (48, 151, 152), PPM (115, 62, 563) y totales (547, 91).
  El **remanente de crédito fiscal se encadena solo** al mes siguiente al guardar.
- **Formulario 22** — determinación de la Renta Líquida Imponible partiendo del
  resultado del balance, con agregados, deducciones, pérdidas de arrastre, PPM y
  créditos. Aplica la tasa de Primera Categoría según el régimen (27% / 25% / liberado).
- Ambos se exportan en PDF, Excel y CSV para traspasarlos al formulario oficial.

### Remuneraciones
- Ficha de trabajadores con contrato, AFP, salud (Fonasa/Isapre con plan en UF),
  seguro de cesantía, cargas familiares y datos bancarios.
- **Liquidación de sueldo** completa: gratificación Art. 50 (25% con tope 4,75 IMM
  anual), topes imponibles en UF (87,8 AFP/salud, 131,9 AFC), cotización AFP por
  administradora, salud 7% + adicional Isapre, AFC según tipo de contrato,
  **Impuesto Único de Segunda Categoría** con la tabla de 8 tramos en UTM,
  asignación familiar por tramo y días proporcionales.
- Aportes del empleador (SIS, AFC empleador, mutual) y **costo empresa** total.
- **Libro de remuneraciones** exportable y **centralización contable** del mes.
- Liquidación individual en PDF con línea de firma.
- Calculadora de **finiquitos**: indemnización por años de servicio (tope 11 años),
  aviso previo y feriado proporcional.

### Activo fijo
- Registro con la **tabla de vidas útiles del SII** (Res. Ex. N°43 de 2002).
- **Depreciación lineal mensual**, normal o **acelerada** (vida útil ÷ 3), comenzando
  el mes siguiente a la adquisición, con valor residual.
- Tabla de depreciación completa por activo y contabilización mensual automática.
- **Bajas y ventas** con cálculo del resultado (utilidad o pérdida en venta).

### Informes
- **Estado de Resultados** por función, con margen bruto, resultado operacional y
  resultado antes de impuesto.
- **Estado de Situación Financiera** clasificado en corriente / no corriente, con
  detección de descuadres.
- **Análisis de cuentas con auxiliar**: saldos pendientes por cliente y proveedor.
- Todo exportable a **PDF, Excel y CSV**, y con hoja de impresión limpia.

### Sistema
- Usuarios con roles (administrador, contador, consulta).
- Respaldos y restauración con un clic (guarda una copia del estado previo antes de
  restaurar).
- Indicadores económicos (UF, UTM, UTA, IPC, ingreso mínimo, dólar) por mes, con
  función para copiar el año anterior como punto de partida.

---

## Advertencia importante

Las propuestas de F29 y F22 son **documentos de trabajo**, no declaraciones. Los códigos
se calculan desde tu contabilidad, pero **el SII modifica los formularios cada año**.
Contrasta siempre los códigos contra el formulario oficial vigente antes de declarar.

Lo mismo aplica a los parámetros previsionales y tributarios: las tasas de AFP, los topes
imponibles en UF, el ingreso mínimo y la tabla de asignación familiar cambian
periódicamente. Revísalos en *Configuración → Parámetros* y actualízalos cuando
corresponda.

---

## Para desarrolladores

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt httpx
.venv/bin/python -m unittest discover -s tests -v   # 66 pruebas
.venv/bin/python run.py                             # levanta la app
```

**Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 · SQLite · Jinja2 · openpyxl ·
reportlab · PyInstaller. Sin dependencias de red en el navegador: todo el CSS y JS
es local, así que la aplicación funciona sin conexión.

```
contaflow/
  config.py          Parámetros tributarios y previsionales, rutas de datos
  database.py        Motor SQLAlchemy (SQLite en modo WAL)
  app.py             Aplicación FastAPI, middleware y manejo de errores
  web.py             Contexto de plantillas, sesión, helpers de descarga
  models/            Modelos ORM (organización, contabilidad, tributario, operaciones)
  services/          Lógica de negocio — el núcleo del sistema
    utils.py            RUT (módulo 11), montos, fechas
    plan_cuentas.py     Plan de cuentas chileno y catálogo de DTE del SII
    contabilidad.py     Motor de asientos, mayor, balance, estados financieros
    documentos.py       IVA y centralización contable de compras/ventas
    libros.py           Libros de IVA y agrupación para el F29
    formularios.py      Propuestas de F29 y F22
    remuneraciones.py   Liquidaciones de sueldo e impuesto único
    activofijo.py       Depreciación y bajas
    exportar.py         CSV, Excel, PDF y respaldos
  routers/           Rutas HTTP
  templates/         Vistas Jinja2
  static/            Hoja de estilos
```

---

## Autoría y licencia

**ContaFlow** fue creado y desarrollado por **Loc0Matt** en 2026.

Se publica bajo licencia **MIT**: puedes usarlo, modificarlo, redistribuirlo y
también comercializarlo. La única condición es conservar el aviso de copyright
del archivo [`LICENSE`](LICENSE). Los detalles están en [`AUTORES.md`](AUTORES.md).

Para comprobar la autoría del sistema:

```bash
python -m contaflow.firma
```

o, con la aplicación en marcha, abre `http://127.0.0.1:8777/firma`.
