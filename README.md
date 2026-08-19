# ContAll — Contabilidad para Todos

> Creado por **Loc0Matt** · 2026 · Código abierto bajo licencia [MIT](LICENSE)

Sistema contable chileno multiempresa completo para llevar una cartera pequeña de
clientes, construido según la normativa chilena. Funciona **100% offline** en tu
computador Windows: no se conecta al SII ni a ningún servicio externo, y todos los
datos viven en un solo archivo en tu disco.

> **¿Venías usando ContaFlow?** Es este mismo proyecto con nombre nuevo desde la
> versión 1.1.0. Actualiza sin miedo: tus datos se detectan solos y no se pierde nada
> (ver [Dónde quedan tus datos](#dónde-quedan-tus-datos)).

Genera **propuestas de formularios** (F29 mensual y F22 anual) con los códigos calculados
desde tu propia contabilidad, para que los uses como base al llenar los formularios
oficiales del SII.

---

## Descargar el ejecutable

### ⬇️ [Descargar ContAll.exe](https://github.com/Loc0Matt/ContaFlow/releases/latest/download/ContAll.exe)

Un clic en el link de arriba y empieza la descarga — no hace falta cuenta de GitHub,
ni saber qué es un repositorio, ni nada técnico. Ese link **siempre entrega la última
versión estable publicada**, aunque en ese momento se esté preparando la siguiente por
otro lado: cada versión queda fija en su propia página, así que nunca vas a bajar algo
a medio terminar.

Cuando termine de descargar:

1. Colócalo donde quieras (Escritorio, `C:\ContAll\`, un pendrive). El `.exe` corre
   igual desde cualquier lado; si quieres que tus datos viajen con él en el pendrive
   (no solo el programa), mira [Modo portable](#modo-portable-llevar-los-datos-en-el-mismo-pendrive) más abajo.
2. Ábrelo con doble clic. **No necesitas instalar Python ni nada más.**
3. Windows SmartScreen puede advertir porque el ejecutable no está firmado digitalmente
   (ocurre con cualquier programa sin certificado de firma comercial paga). Elige
   **Más información → Ejecutar de todas formas**.

El manual de usuario (48 páginas, con índice clickeable, explica cada apartado del
sistema y las 145 cuentas del plan contable una por una) **ya viaja dentro del propio
`ContAll.exe`** — ábrelo desde *Manual de usuario* en el menú lateral del programa, sin
descargar nada aparte. Si prefieres tenerlo suelto (para leerlo en otro dispositivo,
por ejemplo), también se descarga solo:

**[📖 Descargar el manual en PDF](https://github.com/Loc0Matt/ContaFlow/releases/latest/download/Manual-ContAll.pdf)**

<details>
<summary><strong>Ver todas las versiones publicadas</strong></summary>

En la [página de Releases](https://github.com/Loc0Matt/ContaFlow/releases) están todas
las versiones anteriores, por si necesitas volver a una en particular.

</details>

### Construirlo tú mismo en Windows

Si prefieres compilarlo en tu propio equipo:

1. Instala [Python 3.11+](https://www.python.org/downloads/) marcando **«Add Python to PATH»**.
2. Descarga el repositorio como ZIP y descomprímelo.
3. Doble clic en **`build\construir_exe.bat`**.

El script crea el entorno, instala dependencias, corre las pruebas y deja el ejecutable
en `dist\ContAll.exe`.

### La versión en desarrollo (para quien quiera probar lo último sin esperar una Release)

Cada vez que se sube un cambio al repositorio, GitHub compila automáticamente un `.exe`
de prueba y lo deja en la pestaña **Actions → (ejecución más reciente) → Artifacts**.
Es la versión más nueva posible, pero puede no estar del todo probada — pensada para
colaboradores, no para uso general. Requiere estar con sesión iniciada en GitHub para
poder descargarla.

---

## Documentación

| Documento | Qué contiene |
|---|---|
| **[`docs/Manual-ContAll.pdf`](docs/Manual-ContAll.pdf)** | Manual completo de 48 páginas para un usuario nuevo: índice clickeable, marcadores en el lector, referencias cruzadas y un **diccionario con las 145 cuentas del plan** — qué registra cada una, cuándo se carga y cuándo se abona. |
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

1. Abre `ContAll.exe`. Se abre **en su propia ventana de escritorio**, sin
   navegador a la vista.
2. Ingresa con **usuario `admin`, contraseña `admin`**.
3. Por seguridad, el sistema te pide **cambiar esa contraseña** antes de dejarte
   seguir — no es opcional, es el único paso obligatorio del primer arranque.
4. Elige tu **perfil**: Emprendedor, Pyme o Contador. Esto ajusta qué tan cargada
   se ve la interfaz — un contador con varios clientes ve todo sin restricciones;
   un emprendedor o pyme parten con un menú más simple (se puede cambiar después
   desde *Perfil*, en el menú lateral). Emprendedor y Pyme administran una sola
   empresa; Contador, todas las que necesites.
5. Crea tu primera empresa en *Empresas → Nueva empresa*. Al guardar se genera
   automáticamente el **plan de cuentas chileno completo** (más de 140 cuentas).
   ¿Aún no tienes RUT de empresa? Puedes usar tu propio RUT de persona natural.
6. Carga la **UF, UTM e ingreso mínimo** del año en *Maestros → Indicadores*
   (sólo necesario si vas a emitir liquidaciones de sueldo).

Para cerrar el sistema, cierra la ventana.

### Modo presentación

Si vas a compartir pantalla con un cliente y quieres mostrarle el sistema sin
riesgo de modificar algo por accidente, activa **Modo presentación** (botón en
la barra superior). Todo el sistema queda en solo lectura hasta que lo
desactives — ningún formulario guarda mientras esté activo.

### Cómo funciona por dentro

ContAll es una aplicación de escritorio, pero su interfaz está hecha con tecnología
web y la dibuja un pequeño servidor que corre **dentro de tu propio computador**. Por eso
existe la dirección `http://127.0.0.1:8777`: es el programa hablando consigo mismo, no
internet. Nadie más puede acceder.

La ventana usa **WebView2**, el motor que Windows 10 y 11 ya traen instalado. Si en tu
equipo faltara, el sistema abre el navegador en «modo aplicación» (una ventana limpia,
sin barra de direcciones ni pestañas) y, como último recurso, el navegador normal con
una ventanita para cerrar el servidor. En cualquiera de los tres casos el programa
funciona igual.

### Dónde quedan tus datos

Desde la v1.1.0, la primera vez que abres `ContAll.exe` se crea **solo, junto al
ejecutable**, una carpeta llamada `datos`:

```
(la carpeta donde tengas ContAll.exe)\datos\contaflow.db
```

Ese único archivo contiene **todas** las empresas. Respáldalo desde
*Configuración → Respaldos* o cópialo a mano. Como el `.exe` y su carpeta `datos`
quedan siempre juntos, puedes mover ambos (por ejemplo a un pendrive) sin perder nada
— ver [Modo portable](#modo-portable-llevar-los-datos-en-el-mismo-pendrive) más abajo.

Si el `.exe` corre desde un lugar sin permiso de escritura (por ejemplo, un CD-ROM o
una carpeta de sólo lectura), no puede crear `datos` ahí y usa en su lugar el AppData
del computador:

```
C:\Users\<tu usuario>\AppData\Local\ContAll\contaflow.db
```

Si vienes de **ContaFlow** (nombre del programa hasta la v1.0.0) con datos ya
guardados en AppData, no necesitas mover nada a mano: ContAll los encuentra solos y
sigue usando esa misma carpeta — no te crea una `datos` vacía por encima.

### Modo portable (llevar los datos en el mismo pendrive)

Desde la v1.1.0 esto es automático para cualquier instalación nueva (ver arriba): el
`.exe` y su carpeta `datos` quedan siempre en el mismo lugar, así que copiar ambos a
un pendrive y abrirlo en otro computador ya trae tus empresas y comprobantes consigo.

Si ya venías usando una versión anterior con tus datos en AppData y quieres pasarte al
modo portable, créala tú mismo: una carpeta llamada **`datos`** en la misma carpeta
donde está `ContAll.exe`. En cuanto exista, ContAll la usa en vez de AppData — así el
`.exe` y sus datos quedan juntos desde ese momento en adelante. Mientras no la crees,
todo sigue exactamente igual que antes, en AppData.

### Actualizar ContAll

No hay actualización automática por internet (el sistema es offline a propósito).
Actualizar es descargar el `.exe` nuevo y reemplazar el viejo — nada más. Como los
datos viven aparte (ver arriba), reemplazar el ejecutable no los toca.

Si una actualización necesita cambiar la estructura de la base de datos (agregar un
campo nuevo a una tabla existente, por ejemplo), ContAll lo detecta y lo aplica solo
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
- Varios usuarios (todos con el mismo nivel de acceso — sirve para saber quién
  hizo cada cambio, no para restringir).
- **Modo presentación**: bloquea toda escritura del sistema con un clic, para
  mostrárselo a un cliente sin riesgo de modificar algo sin querer.
- **Perfil de instalación** (Emprendedor / Pyme / Contador): ajusta qué tan
  cargada se ve la interfaz y cuántas empresas se pueden administrar.
- Contraseña inicial obligatoria de cambiar, y bloqueo temporal tras varios
  intentos fallidos de inicio de sesión.
- Respaldos y restauración con un clic (guarda una copia del estado previo antes de
  restaurar), con respaldo automático antes de aplicar cualquier actualización
  que cambie la estructura de la base de datos.
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
.venv/bin/python -m unittest discover -s tests -v   # 185+ pruebas
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

## Historial de versiones

Resumen de qué cambia en cada versión publicada. El detalle línea por línea está en
los commits y en la [página de Releases](https://github.com/Loc0Matt/ContaFlow/releases).

### 1.1.0 — Cambio de nombre a ContAll, sin roles y modo presentación

- **Cambio de nombre**: el proyecto pasa de llamarse ContaFlow a **ContAll —
  Contabilidad para Todos**. Quien actualice conserva sus datos sin hacer nada (ver
  [Dónde quedan tus datos](#dónde-quedan-tus-datos)).
- **Se eliminan los roles**: ya no existen Admin/Contador/Consulta — todos los
  usuarios tienen el mismo nivel de acceso.
- **Modo presentación**: un botón en la barra superior bloquea toda escritura del
  sistema, para mostrárselo a un cliente sin riesgo de modificar algo sin querer.
- **Asistente de perfil inicial** (Emprendedor / Pyme / Contador): ajusta qué tan
  cargada se ve la interfaz. Emprendedor y Pyme quedan limitados a una empresa;
  Contador administra todas las que necesite.
- **Seguridad de acceso**: cambio de contraseña obligatorio en el primer inicio de
  sesión, bloqueo temporal tras varios intentos fallidos y un mínimo de contraseña
  consistente en todo el sistema.
- **Modo portable de fábrica**: en una instalación nueva, el propio `.exe` crea solo
  su carpeta `datos` al lado — los datos viajan con él entre computadores (por
  ejemplo, en un pendrive) sin ningún paso manual.
- **Liquidaciones de sueldo editables y eliminables**: se puede quitar una
  liquidación calculada por error, y corregirla (recalculándola) ya no falla ni deja
  el asiento de centralización desactualizado.
- **Manual de usuario incrustado en el `.exe`**: se abre desde el menú lateral del
  programa, sin depender de bajarlo aparte.
- Corrección de condiciones de carrera al numerar comprobantes y folios de
  documentos, para que un choque dé un mensaje claro en vez de un error interno.
- La clave de firma de las cookies de sesión ahora es aleatoria y persistida, en vez
  de derivarse de la ruta de la base de datos.
- Ya no se puede seleccionar una empresa desactivada, ni cerrar dos veces el mismo
  ejercicio contable.

### 1.0.0 — Primera versión pública

Primera versión estable de la aplicación de escritorio: contabilidad multiempresa
completa según la normativa chilena (plan de cuentas, libros, IVA, Formularios 29 y
22, remuneraciones, activo fijo e informes), empaquetada como un único `.exe` para
Windows, sin dependencias de red y con control de versión de esquema y respaldo
automático de la base de datos.

---

## Autoría y licencia

**ContAll** fue creado y desarrollado por **Loc0Matt** en 2026.

Se publica bajo licencia **MIT**: puedes usarlo, modificarlo, redistribuirlo y
también comercializarlo. La única condición es conservar el aviso de copyright
del archivo [`LICENSE`](LICENSE). Los detalles están en [`AUTORES.md`](AUTORES.md).

Para comprobar la autoría del sistema:

```bash
python -m contaflow.firma
```

o, con la aplicación en marcha, abre `http://127.0.0.1:8777/firma`.
