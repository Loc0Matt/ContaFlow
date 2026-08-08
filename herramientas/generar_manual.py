"""Genera el manual de usuario de ContaFlow en PDF.

Produce `docs/Manual-ContaFlow.pdf` con índice clickeable, marcadores en el
panel lateral del lector, referencias cruzadas internas y enlaces externos.

    python herramientas/generar_manual.py [ruta-de-salida.pdf]
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, CondPageBreak, Frame, KeepTogether, ListFlowable, ListItem, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

from contaflow.config import (  # noqa: E402
    APP_NAME, APP_VERSION, RETENCION_HONORARIOS, TABLA_IMPUESTO_UNICO_UTM, TASAS_AFC,
    TASA_SALUD_LEGAL, TASA_SIS_EMPLEADOR, TOPE_IMPONIBLE_AFC_UF, TOPE_IMPONIBLE_AFP_UF,
)
from contaflow.services.activofijo import VIDAS_UTILES_SII  # noqa: E402
from contaflow.services.glosario import GLOSARIO_CUENTAS, cuentas_sin_glosario  # noqa: E402
from contaflow.services.plan_cuentas import CUENTAS_DEFECTO, PLAN_CUENTAS, TIPOS_DTE  # noqa: E402

AZUL = colors.HexColor("#1F3864")
AZUL_CLARO = colors.HexColor("#2F5597")
ACENTO = colors.HexColor("#0D9488")
GRIS = colors.HexColor("#F5F7FA")
BORDE = colors.HexColor("#C8D2E0")
TEXTO_SUAVE = colors.HexColor("#555555")
AMBAR = colors.HexColor("#8A6D3B")
AMBAR_FONDO = colors.HexColor("#FDF6E3")


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------


def crear_estilos():
    base = getSampleStyleSheet()
    e = {}
    e["cuerpo"] = ParagraphStyle(
        "cuerpo", parent=base["BodyText"], fontSize=9.5, leading=13.5,
        alignment=TA_JUSTIFY, spaceAfter=6,
    )
    e["h1"] = ParagraphStyle(
        "h1", parent=base["Heading1"], fontSize=19, leading=23, textColor=AZUL,
        spaceBefore=0, spaceAfter=10,
    )
    e["h2"] = ParagraphStyle(
        "h2", parent=base["Heading2"], fontSize=13.5, leading=17, textColor=AZUL,
        spaceBefore=14, spaceAfter=6,
    )
    e["h3"] = ParagraphStyle(
        "h3", parent=base["Heading3"], fontSize=10.5, leading=14, textColor=AZUL_CLARO,
        spaceBefore=10, spaceAfter=4,
    )
    e["celda"] = ParagraphStyle("celda", parent=base["BodyText"], fontSize=8, leading=10.5,
                                spaceAfter=0)
    e["celda_cab"] = ParagraphStyle("celda_cab", parent=e["celda"], textColor=colors.white,
                                    fontName="Helvetica-Bold")
    e["celda_mono"] = ParagraphStyle("celda_mono", parent=e["celda"], fontName="Courier-Bold",
                                     fontSize=7.5)
    e["nota"] = ParagraphStyle(
        "nota", parent=e["cuerpo"], fontSize=8.5, leading=12, textColor=AMBAR,
        leftIndent=8, rightIndent=8, spaceBefore=2, spaceAfter=2, alignment=TA_JUSTIFY,
    )
    e["lista"] = ParagraphStyle("lista", parent=e["cuerpo"], spaceAfter=3, alignment=TA_JUSTIFY)
    e["portada_titulo"] = ParagraphStyle(
        "pt", parent=base["Title"], fontSize=40, leading=44, textColor=AZUL, alignment=TA_CENTER,
    )
    e["portada_sub"] = ParagraphStyle(
        "ps", parent=base["Normal"], fontSize=14, leading=20, textColor=AZUL_CLARO,
        alignment=TA_CENTER, spaceBefore=6,
    )
    e["portada_pie"] = ParagraphStyle(
        "pp", parent=base["Normal"], fontSize=9, leading=14, textColor=TEXTO_SUAVE,
        alignment=TA_CENTER,
    )
    e["toc1"] = ParagraphStyle("toc1", fontSize=10.5, leading=17, textColor=AZUL,
                               fontName="Helvetica-Bold")
    e["toc2"] = ParagraphStyle("toc2", fontSize=9.5, leading=14, leftIndent=14,
                               textColor=colors.HexColor("#333333"))
    e["toc3"] = ParagraphStyle("toc3", fontSize=9, leading=12.5, leftIndent=30,
                               textColor=TEXTO_SUAVE)
    return e


EST = crear_estilos()


# ---------------------------------------------------------------------------
# Plantilla del documento (marcadores, índice y pie de página)
# ---------------------------------------------------------------------------


class ManualDoc(BaseDocTemplate):
    """Documento que registra marcadores y entradas de índice automáticamente."""

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        nivel = {"h1": 0, "h2": 1, "h3": 2}.get(flowable.style.name)
        if nivel is None:
            return
        clave = getattr(flowable, "_ancla", None)
        if not clave:
            return
        texto = flowable.getPlainText()
        # La misma clave, como texto plano, en los tres lugares: el marcador de
        # página, la entrada del panel lateral y el enlace del índice. Si se
        # codifica a bytes en uno de ellos, reportlab crea destinos distintos y
        # los enlaces terminan apuntando a la página equivocada.
        self.canv.bookmarkPage(clave)
        self.canv.addOutlineEntry(texto, clave, level=nivel, closed=(nivel == 0))
        # El 4º elemento de la tupla hace clickeable la entrada del índice.
        self.notify("TOCEntry", (nivel, texto, self.page, clave))


def dibujar_pie(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXTO_SUAVE)
    canvas.drawString(18 * mm, 10.5 * mm, f"{APP_NAME} {APP_VERSION} · Manual de usuario")
    canvas.drawRightString(A4[0] - 18 * mm, 10.5 * mm, f"Página {doc.page}")
    canvas.restoreState()


def dibujar_portada(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(AZUL)
    canvas.rect(0, A4[1] - 95 * mm, A4[0], 95 * mm, stroke=0, fill=1)
    canvas.setFillColor(ACENTO)
    canvas.rect(0, A4[1] - 99 * mm, A4[0], 4 * mm, stroke=0, fill=1)
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Constructores de contenido
# ---------------------------------------------------------------------------

_anclas: set[str] = set()


def titulo(texto: str, nivel: int, ancla: str):
    """Título con marcador, para que aparezca en el índice y en el panel lateral."""
    _anclas.add(ancla)
    p = Paragraph(texto, EST[f"h{nivel}"])
    p._ancla = ancla
    return p


def enlace(texto: str, ancla: str) -> str:
    """Referencia interna clickeable a otra sección del manual."""
    return f'<a href="#{ancla}" color="#2F5597"><u>{texto}</u></a>'


def externo(texto: str, url: str) -> str:
    return f'<a href="{url}" color="#0D9488"><u>{texto}</u></a>'


def parrafo(texto: str, estilo="cuerpo"):
    return Paragraph(texto, EST[estilo])


def vinetas(items: list[str]):
    # bulletOffsetY negativo baja la viñeta hasta la línea base del texto;
    # con valores positivos queda flotando sobre el primer renglón.
    return ListFlowable(
        [ListItem(Paragraph(t, EST["lista"]), leftIndent=12) for t in items],
        bulletType="bullet", bulletFontSize=7, bulletOffsetY=-2.5,
        leftIndent=14, spaceBefore=2, spaceAfter=7,
    )


def numerada(items: list[str]):
    return ListFlowable(
        [ListItem(Paragraph(t, EST["lista"]), leftIndent=14) for t in items],
        bulletType="1", bulletFormat="%s.", bulletFontSize=9.5, bulletOffsetY=-1,
        leftIndent=16, spaceBefore=2, spaceAfter=7,
    )


def aviso(texto: str):
    """Recuadro de advertencia."""
    t = Table([[Paragraph(f"<b>Atención.</b> {texto}", EST["nota"])]],
              colWidths=[171 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AMBAR_FONDO),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E5D3A1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 7)])


def tabla(encabezados: list[str], filas: list[list], anchos: list[float],
          monoprimera: bool = False, tam: float = 8):
    datos = [[Paragraph(str(h), EST["celda_cab"]) for h in encabezados]]
    for fila in filas:
        celdas = []
        for i, valor in enumerate(fila):
            estilo = "celda_mono" if (monoprimera and i == 0) else "celda"
            celdas.append(Paragraph(str(valor), EST[estilo]))
        datos.append(celdas)
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return KeepTogether([t, Spacer(1, 8)]) if len(filas) <= 6 else t


def ruta(texto: str) -> str:
    """Resalta una ruta de menú del sistema."""
    return f'<font color="#0D9488"><b>{texto}</b></font>'


def cta(codigo: str) -> str:
    return f'<font face="Courier-Bold" size="8.5">{codigo}</font>'


# ---------------------------------------------------------------------------
# Secciones del manual
# ---------------------------------------------------------------------------


def portada():
    return [
        Spacer(1, 32 * mm),
        Paragraph(f'<font color="white">{APP_NAME}</font>', EST["portada_titulo"]),
        Paragraph('<font color="#A8B8D8">Sistema Contable Chileno Multiempresa</font>',
                  EST["portada_sub"]),
        Spacer(1, 42 * mm),
        Paragraph("Manual de usuario", ParagraphStyle(
            "mu", parent=EST["portada_titulo"], fontSize=26, textColor=AZUL)),
        Paragraph("Guía completa para empezar desde cero", EST["portada_sub"]),
        Spacer(1, 14 * mm),
        Paragraph(
            "Este manual explica, paso a paso, cómo funciona cada apartado del sistema y "
            "para qué sirve cada una de las cuentas del plan contable. Está escrito para "
            "alguien que abre ContaFlow por primera vez.",
            ParagraphStyle("intro", parent=EST["cuerpo"], alignment=TA_CENTER,
                           leftIndent=22 * mm, rightIndent=22 * mm, fontSize=10)),
        Spacer(1, 22 * mm),
        Paragraph(
            f"Versión {APP_VERSION} · {date.today():%d-%m-%Y}<br/>"
            f"{len(GLOSARIO_CUENTAS)} cuentas documentadas",
            EST["portada_pie"]),
        NextPageTemplate("indice"),
        PageBreak(),
    ]


def indice():
    toc = TableOfContents()
    toc.levelStyles = [EST["toc1"], EST["toc2"], EST["toc3"]]
    toc.dotsMinLevel = 0
    return [
        Paragraph("Índice", ParagraphStyle("ti", parent=EST["h1"], spaceAfter=14)),
        Paragraph("Haz clic en cualquier línea para saltar directamente a esa sección. "
                  "El lector de PDF también muestra el índice en su panel lateral.",
                  ParagraphStyle("ai", parent=EST["cuerpo"], textColor=TEXTO_SUAVE,
                                 fontSize=8.5, spaceAfter=12)),
        toc,
        NextPageTemplate("normal"),
        PageBreak(),
    ]


def cap_bienvenida():
    return [
        titulo("1. Bienvenido a ContaFlow", 1, "cap1"),
        parrafo(
            "ContaFlow es un sistema de contabilidad completo que corre <b>en tu propio "
            "computador</b>. No necesita internet, no envía tus datos a ningún servidor y "
            "está pensado para llevar la contabilidad de varias empresas pequeñas a la vez."
        ),

        titulo("1.1 Qué hace y qué no hace", 2, "cap1-1"),
        parrafo("<b>Lo que hace:</b>"),
        vinetas([
            "Registra tus compras, ventas, boletas de honorarios y asientos contables.",
            "Genera solo los asientos contables de cada documento, ya cuadrados.",
            "Arma los libros de compras y ventas del IVA en el formato de columnas del SII.",
            "Calcula una <b>propuesta</b> del Formulario 29 mensual y del Formulario 22 anual.",
            "Liquida sueldos con todas las cotizaciones y el Impuesto Único.",
            "Lleva el activo fijo y calcula su depreciación mes a mes.",
            "Entrega balances, estado de resultados y análisis de cuentas.",
            "Exporta todo a PDF, Excel y CSV.",
        ]),
        parrafo("<b>Lo que no hace:</b>"),
        vinetas([
            "No se conecta al SII. No emite documentos tributarios electrónicos ni "
            "descarga los que recibes: los documentos se ingresan a mano.",
            "No presenta declaraciones. Las propuestas de F29 y F22 son para que "
            "traspases los valores al formulario oficial.",
            "No reemplaza el criterio de un contador. Decide él qué es gasto aceptado, "
            "qué se agrega a la renta líquida y cómo se clasifica cada operación.",
        ]),
        aviso(
            "El SII modifica sus formularios y los organismos previsionales cambian sus "
            "tasas todos los años. Antes de declarar, contrasta los códigos que entrega el "
            "sistema con el formulario oficial vigente, y revisa los parámetros en "
            f"{ruta('Configuración → Parámetros')}. Ver {enlace('§17.2 Parámetros', 'cap17-2')}."
        ),

        titulo("1.2 Instalar y abrir", 2, "cap1-2"),
        parrafo(
            "ContaFlow es un solo archivo: <b>ContaFlow.exe</b>. No tiene instalador ni "
            "deja rastros en el registro de Windows."
        ),
        numerada([
            "Copia <b>ContaFlow.exe</b> donde quieras: el Escritorio, una carpeta como "
            "<font face='Courier'>C:\\ContaFlow\\</font>, incluso un pendrive.",
            "Haz doble clic sobre él.",
            "La primera vez Windows puede mostrar una advertencia de SmartScreen porque el "
            "programa no tiene firma digital comercial. Elige <b>Más información</b> y luego "
            "<b>Ejecutar de todas formas</b>.",
            "Se abrirá una ventanita azul de control y, enseguida, tu navegador con el sistema.",
        ]),

        titulo("1.3 La ventana de control", 2, "cap1-3"),
        parrafo(
            "La ventanita azul <b>es el sistema corriendo</b>. Mientras esté abierta, "
            "ContaFlow funciona; si la cierras, se apaga. Puedes minimizarla sin problema."
        ),
        vinetas([
            "<b>Abrir ContaFlow</b> — vuelve a abrir la pantalla en tu navegador, por si la "
            "cerraste por accidente.",
            "<b>Salir</b> — apaga el sistema. Úsalo cuando termines de trabajar.",
        ]),
        parrafo(
            "Si prefieres, puedes escribir directamente "
            "<font face='Courier'>http://127.0.0.1:8777</font> en tu navegador. Esa dirección "
            "apunta a tu propio computador: nadie más puede entrar."
        ),

        titulo("1.4 Primer ingreso", 2, "cap1-4"),
        parrafo(
            "El sistema parte con un solo usuario: <b>admin</b>, contraseña <b>admin</b>. "
            "Cámbiala apenas entres, en "
            f"{ruta('Configuración → Respaldos → Cambiar mi contraseña')}."
        ),

        titulo("1.5 Dónde quedan tus datos", 2, "cap1-5"),
        parrafo("Todo lo que registres vive en un único archivo:"),
        parrafo(
            "<font face='Courier' size='8.5'>C:\\Users\\&lt;tu usuario&gt;\\AppData\\Local\\"
            "ContaFlow\\contaflow.db</font>"
        ),
        parrafo(
            "Ese archivo contiene <b>todas</b> las empresas. Está fuera del ejecutable a "
            "propósito: si mañana reemplazas ContaFlow.exe por una versión nueva, tus datos "
            "siguen intactos. Respáldalo seguido — ver "
            f"{enlace('§17.4 Respaldos', 'cap17-4')}."
        ),

        titulo("1.6 Cómo se recorre la pantalla", 2, "cap1-6"),
        parrafo("Hay tres zonas y conviene entenderlas antes de seguir:"),
        tabla(
            ["Zona", "Para qué sirve"],
            [
                ["<b>Menú lateral azul</b>",
                 "Todas las secciones del sistema, agrupadas por tema: Tributario, "
                 "Contabilidad, Informes, Remuneraciones, Maestros y Sistema."],
                ["<b>Barra superior</b>",
                 "Los dos selectores más importantes: la <b>empresa</b> en la que trabajas y "
                 "el <b>período</b> (mes y año). Casi todas las pantallas muestran los datos "
                 "de la empresa y el período elegidos aquí."],
                ["<b>Zona central</b>",
                 "El contenido de la sección abierta. Los mensajes verdes confirman lo que "
                 "acabas de hacer; los rojos avisan de un error."],
            ],
            [34 * mm, 137 * mm],
        ),
        aviso(
            "El selector de <b>período</b> de la barra superior manda sobre casi todo. Si "
            "registras una venta y no aparece en el libro, lo más probable es que estés "
            "mirando otro mes. Revísalo siempre antes de dar algo por perdido."
        ),
    ]


def cap_conceptos():
    return [
        PageBreak(),
        titulo("2. Contabilidad en diez minutos", 1, "cap2"),
        parrafo(
            "Si nunca has llevado contabilidad, este capítulo te da lo mínimo para entender "
            "qué está haciendo el sistema. Si ya sabes, puedes saltar directamente al "
            f"{enlace('capítulo 3', 'cap3')}."
        ),

        titulo("2.1 Debe, haber y partida doble", 2, "cap2-1"),
        parrafo(
            "Toda operación se anota <b>dos veces</b>: de dónde salió el valor y a dónde "
            "fue. La columna izquierda se llama <b>debe</b> y la derecha <b>haber</b>. "
            "La regla de oro es que en cada asiento la suma del debe tiene que ser "
            "exactamente igual a la del haber."
        ),
        parrafo(
            "Ejemplo: vendes $1.190.000 a crédito (neto $1.000.000 más IVA $190.000)."
        ),
        tabla(
            ["Cuenta", "Debe", "Haber"],
            [
                ["1.1.02.001 Clientes Nacionales", "1.190.000", ""],
                ["4.1.01.001 Ventas Afectas", "", "1.000.000"],
                ["2.1.03.001 IVA Débito Fiscal", "", "190.000"],
                ["<b>Totales</b>", "<b>1.190.000</b>", "<b>1.190.000</b>"],
            ],
            [101 * mm, 35 * mm, 35 * mm],
        ),
        parrafo(
            "El cliente te debe el total con IVA (por eso está al debe), tu ingreso real es "
            "el neto y el IVA no es tuyo: lo recaudas para el Fisco, así que es una deuda. "
            "<b>ContaFlow arma este asiento solo</b> cada vez que registras una venta."
        ),

        titulo("2.2 Los cinco tipos de cuenta", 2, "cap2-2"),
        tabla(
            ["Tipo", "Qué representa", "Aumenta al…", "Ejemplos"],
            [
                ["<b>Activo</b>", "Lo que la empresa tiene o le deben", "Debe",
                 "Caja, banco, clientes, mercaderías, vehículos"],
                ["<b>Pasivo</b>", "Lo que la empresa debe", "Haber",
                 "Proveedores, préstamos, IVA por pagar, sueldos por pagar"],
                ["<b>Patrimonio</b>", "Lo que aportaron los dueños más lo ganado", "Haber",
                 "Capital pagado, utilidades acumuladas"],
                ["<b>Ganancia</b>", "Ingresos del período", "Haber",
                 "Ventas afectas, intereses ganados"],
                ["<b>Pérdida</b>", "Costos y gastos del período", "Debe",
                 "Arriendos, sueldos, costo de ventas, depreciación"],
            ],
            [24 * mm, 51 * mm, 20 * mm, 76 * mm],
        ),
        parrafo(
            "La ecuación que siempre se cumple: <b>Activo = Pasivo + Patrimonio</b>. Si tu "
            "balance no cuadra, algo se imputó donde no correspondía."
        ),

        titulo("2.3 Cuentas imputables y de agrupación", 2, "cap2-3"),
        parrafo(
            "El plan de cuentas es un árbol. Las ramas (<b>1</b>, <b>1.1</b>, <b>1.1.01</b>) "
            "solo agrupan y suman; las hojas (<b>1.1.01.001</b>) son las <b>imputables</b>, "
            "las únicas que reciben movimientos. Si intentas usar una cuenta de agrupación, "
            "el sistema la rechaza y te avisa."
        ),

        titulo("2.4 Auxiliar y centro de costo", 2, "cap2-4"),
        vinetas([
            "<b>Auxiliar</b> — el cliente o proveedor asociado al movimiento. Cuentas como "
            "«Clientes Nacionales» lo exigen: sin él no sabrías <i>quién</i> te debe. "
            "Es lo que permite el informe de "
            f"{enlace('análisis de cuentas', 'cap10-3')}.",
            "<b>Centro de costo</b> — opcional, sirve para separar ingresos y gastos por "
            "área, sucursal o proyecto (Administración, Ventas, Obra Norte…).",
        ]),

        titulo("2.5 Cómo leer un saldo", 2, "cap2-5"),
        parrafo(
            "El saldo es la diferencia entre lo cargado y lo abonado. Un saldo <b>deudor</b> "
            "(debe &gt; haber) es normal en activos y gastos; un saldo <b>acreedor</b> "
            "(haber &gt; debe) es normal en pasivos, patrimonio e ingresos. Cuando una cuenta "
            "muestra el saldo al revés de lo esperado, casi siempre hay un error de imputación."
        ),
    ]


def cap_puesta_en_marcha():
    filas_regimen = [
        ["<b>14 A</b><br/>Semi Integrado", "27%",
         "Empresas grandes o con socios extranjeros. Los dueños usan como crédito solo "
         "el 65% del impuesto pagado por la empresa."],
        ["<b>14 D N°3</b><br/>Pro Pyme General", "25%",
         "El más habitual en PyMEs. Contabilidad completa, crédito total para los dueños. "
         "Es el que trae el sistema por defecto."],
        ["<b>14 D N°8</b><br/>Pro Pyme Transparente", "Liberado",
         "La empresa no paga Primera Categoría: la renta se asigna directamente a los "
         "dueños, que tributan en su Global Complementario."],
        ["<b>Renta Presunta</b>", "25%",
         "Actividades como agricultura, transporte y minería que cumplen los requisitos "
         "para tributar sobre una renta presunta, no la efectiva."],
        ["<b>Segunda Categoría</b>", "—",
         "Profesionales independientes que emiten boletas de honorarios."],
    ]
    return [
        PageBreak(),
        titulo("3. Puesta en marcha", 1, "cap3"),
        parrafo(
            "Estos siete pasos se hacen <b>una sola vez por empresa</b>. Después ya solo "
            "trabajas el día a día."
        ),

        titulo("3.1 Crear la empresa", 2, "cap3-1"),
        parrafo(f"Ve a {ruta('Empresas → Nueva empresa')}. Campo por campo:"),
        tabla(
            ["Campo", "Qué poner"],
            [
                ["RUT", "El RUT de la empresa. Se valida el dígito verificador, así que si "
                        "te equivocas el sistema no te deja guardar. Puedes escribirlo con "
                        "o sin puntos."],
                ["Razón social", "El nombre legal, tal como aparece en el SII."],
                ["Nombre de fantasía", "Opcional, el nombre comercial."],
                ["Giro", "La actividad declarada."],
                ["Código actividad", "El código de actividad económica del SII (6 dígitos)."],
                ["Fecha inicio de actividades", "La del aviso de inicio en el SII."],
                ["Régimen tributario", "Determina la tasa que aplicará el Formulario 22. "
                                       "Ver la tabla siguiente."],
                ["Tasa de PPM", "El porcentaje de tus ventas netas que enteras mensualmente "
                                "como anticipo del impuesto anual. Si no la sabes, mírala en "
                                "tu último F29: es el código 115."],
                ["Contabilidad completa", "Déjala marcada salvo que la empresa lleve "
                                          "contabilidad simplificada."],
            ],
            [40 * mm, 131 * mm],
        ),
        parrafo(
            "Al guardar, el sistema crea automáticamente el <b>plan de cuentas chileno "
            "completo</b> — 145 cuentas imputables listas para usar — más un centro de costo "
            "«General» y toda la configuración contable por defecto. Ya puedes registrar "
            f"documentos. El detalle está en el {enlace('capítulo 4', 'cap4')}."
        ),

        titulo("3.2 Los regímenes tributarios", 2, "cap3-2"),
        tabla(["Régimen", "1ª Cat.", "Cuándo corresponde"], filas_regimen,
              [38 * mm, 18 * mm, 115 * mm]),

        titulo("3.3 Cargar los indicadores (UF, UTM, ingreso mínimo)", 2, "cap3-3"),
        parrafo(
            f"En {ruta('Maestros → Indicadores')} cargas los valores mes a mes. Como el "
            "sistema trabaja sin conexión, estos datos se ingresan a mano."
        ),
        tabla(
            ["Indicador", "Para qué se usa"],
            [
                ["<b>UF</b> (último día del mes)",
                 "Topes imponibles de AFP, salud y seguro de cesantía, y el valor del plan "
                 "de Isapre pactado en UF."],
                ["<b>UTM</b> del mes",
                 "La tabla del Impuesto Único de Segunda Categoría está expresada en UTM."],
                ["<b>Ingreso mínimo</b>",
                 "Tope de la gratificación legal del Art. 50 (4,75 ingresos mínimos al año)."],
                ["<b>UTA, IPC, dólar</b>",
                 "Referencia para cálculos anuales y corrección monetaria."],
            ],
            [45 * mm, 126 * mm],
        ),
        aviso(
            "Sin la UF, la UTM y el ingreso mínimo del mes <b>no se pueden emitir "
            "liquidaciones de sueldo</b>: el sistema se detiene y te dice cuál falta. Si no "
            "tienes trabajadores, puedes saltarte este paso."
        ),
        parrafo(
            "El botón <b>Copiar de otro año</b> duplica los valores del año anterior como "
            "punto de partida; después ajustas mes a mes."
        ),

        titulo("3.4 Revisar las cuentas por defecto", 2, "cap3-4"),
        parrafo(
            f"En {ruta('Configuración → Cuentas por defecto')} decides qué cuenta usa cada "
            "asiento automático. Vienen todas configuradas, así que puedes dejarlas tal "
            "cual. Cámbialas si tu forma de trabajar es distinta: por ejemplo, si llevas "
            "inventario permanente querrás que las compras vayan a «Mercaderías» "
            f"({cta('1.1.05.001')}) en lugar de «Compras del giro» ({cta('5.1.01.005')}). "
            f"La lista completa está en {enlace('§17.1', 'cap17-1')}."
        ),

        titulo("3.5 Centros de costo", 2, "cap3-5"),
        parrafo(
            f"Opcional. En {ruta('Maestros → Centros de costo')} creas las áreas por las que "
            "quieras separar ingresos y gastos. Si no los necesitas, deja solo el «General» "
            "que viene creado."
        ),

        titulo("3.6 Clientes y proveedores", 2, "cap3-6"),
        parrafo(
            f"En {ruta('Maestros → Clientes y proveedores')} puedes cargarlos por adelantado, "
            "pero <b>no es necesario</b>: cuando registras un documento con un RUT nuevo, el "
            "sistema crea la ficha solo. Todos los RUT se validan con módulo 11."
        ),

        titulo("3.7 Usuarios", 2, "cap3-7"),
        parrafo(
            f"Si más de una persona va a usar el sistema, crea usuarios en "
            f"{ruta('Configuración → Usuarios')}. Ver {enlace('§17.3', 'cap17-3')}."
        ),
    ]


def cap_plan_cuentas():
    grupos = {
        "1.1.01": "Efectivo y equivalentes al efectivo",
        "1.1.02": "Deudores comerciales y otras cuentas por cobrar",
        "1.1.03": "Cuentas por cobrar a relacionadas y personal",
        "1.1.04": "Impuestos por recuperar",
        "1.1.05": "Existencias",
        "1.1.06": "Pagos anticipados",
        "1.2.01": "Propiedades, planta y equipo",
        "1.2.02": "Depreciación acumulada",
        "1.2.03": "Activos intangibles",
        "1.2.04": "Inversiones y otros activos",
        "2.1.01": "Obligaciones financieras de corto plazo",
        "2.1.02": "Acreedores comerciales y otras cuentas por pagar",
        "2.1.03": "Impuestos por pagar",
        "2.1.04": "Obligaciones previsionales y con el personal",
        "2.1.05": "Provisiones y otros pasivos",
        "2.2.01": "Obligaciones de largo plazo",
        "3.1.01": "Capital",
        "3.1.02": "Reservas",
        "3.1.03": "Resultados",
        "4.1.01": "Ingresos por ventas",
        "4.2.01": "Ingresos fuera de explotación",
        "5.1.01": "Costo de ventas",
        "5.2.01": "Gastos del personal",
        "5.2.02": "Gastos generales",
        "5.2.03": "Depreciaciones, amortizaciones y castigos",
        "5.3.01": "Gastos no operacionales",
        "5.4.01": "Impuesto a la renta",
        "9.1.01": "Cuentas de orden",
    }
    nombres = {c: n for c, n, _t, _i, _f in PLAN_CUENTAS}

    elementos = [
        PageBreak(),
        titulo("4. El plan de cuentas", 1, "cap4"),
        parrafo(
            "El plan de cuentas es la columna vertebral de la contabilidad: la lista de "
            "«cajones» donde se guarda cada peso. ContaFlow trae uno completo, basado en la "
            "estructura chilena habitual para PyMEs, y lo crea automáticamente al dar de "
            "alta cada empresa."
        ),

        titulo("4.1 Cómo está codificado", 2, "cap4-1"),
        parrafo("El código dice todo sobre la cuenta. Tomemos "
                f"{cta('1.1.01.003')} «Banco Cuenta Corriente»:"),
        tabla(
            ["Nivel", "Código", "Significa"],
            [
                ["1", cta("1"), "Grupo mayor: <b>1</b> Activos, <b>2</b> Pasivos, "
                                "<b>3</b> Patrimonio, <b>4</b> Ingresos, <b>5</b> Costos y "
                                "gastos, <b>9</b> Cuentas de orden"],
                ["2", cta("1.1"), "Subgrupo: corriente / no corriente"],
                ["3", cta("1.1.01"), "Rubro: efectivo y equivalentes"],
                ["4", cta("1.1.01.003"), "La cuenta imputable, donde se registra el movimiento"],
            ],
            [14 * mm, 30 * mm, 127 * mm],
        ),
        parrafo(
            f"Solo el cuarto nivel recibe movimientos. Ver "
            f"{enlace('§2.3 Cuentas imputables y de agrupación', 'cap2-3')}."
        ),

        titulo("4.2 Agregar o modificar cuentas", 2, "cap4-2"),
        parrafo(
            f"En {ruta('Maestros → Plan de cuentas')}, despliega <b>Agregar o modificar una "
            "cuenta</b>. El nivel y la cuenta madre se deducen solos de los puntos del "
            "código: si escribes <b>5.2.02.018</b>, quedará colgando de <b>5.2.02</b> "
            "«Gastos Generales»."
        ),
        parrafo("Las cuatro casillas de cada cuenta:"),
        tabla(
            ["Casilla", "Qué provoca"],
            [
                ["<b>Imputable</b>", "Permite registrar movimientos en ella. Si la desmarcas, "
                                     "la cuenta pasa a ser solo un título que agrupa."],
                ["<b>Exige cliente/proveedor</b>",
                 "Obliga a indicar el auxiliar en cada movimiento. Actívala en cuentas de "
                 "clientes, proveedores y anticipos: es lo que después permite saber quién "
                 "te debe."],
                ["<b>Exige centro de costo</b>",
                 "Obliga a indicar el centro de costo. Útil en cuentas de gasto cuando "
                 "quieres control por área."],
                ["<b>Es cuenta bancaria</b>",
                 "Hace que la cuenta aparezca en la conciliación bancaria."],
            ],
            [45 * mm, 126 * mm],
        ),
        aviso(
            "No borres cuentas que ya tengan movimientos. Si dejaste de usar una, "
            "<b>desactívala</b>: desaparece de los formularios pero su historia se conserva."
        ),

        titulo("4.3 Diccionario de cuentas", 2, "cap4-3"),
        parrafo(
            "Aquí está el detalle de las <b>145 cuentas imputables</b> del plan: qué registra "
            "cada una, cuándo se carga y cuándo se abona. Es la sección para consultar cada "
            "vez que dudes dónde va una operación."
        ),
        parrafo(
            "Recuerda la regla general: <b>cargar</b> (debe) aumenta activos y gastos; "
            "<b>abonar</b> (haber) aumenta pasivos, patrimonio e ingresos.",
        ),
        Spacer(1, 4),
    ]

    for prefijo, titulo_grupo in grupos.items():
        cuentas = [
            (c, nombres[c]) for c, _n, _t, imputable, _f in PLAN_CUENTAS
            if imputable and c.startswith(prefijo + ".")
        ]
        if not cuentas:
            continue
        elementos.append(CondPageBreak(45 * mm))
        elementos.append(titulo(f"{prefijo} · {titulo_grupo}", 3, f"grupo-{prefijo}"))
        filas = []
        for codigo, nombre in cuentas:
            uso, carga, abona = GLOSARIO_CUENTAS[codigo]
            filas.append([
                f"{codigo}<br/><br/><font face='Helvetica-Bold' size='7.5'>{nombre}</font>",
                uso, carga, abona,
            ])
        elementos.append(tabla(
            ["Cuenta", "Qué registra", "Se carga (Debe) cuando…", "Se abona (Haber) cuando…"],
            filas, [30 * mm, 49 * mm, 46 * mm, 46 * mm], monoprimera=True,
        ))
        elementos.append(Spacer(1, 6))

    return elementos


def cap_ventas():
    return [
        PageBreak(),
        titulo("5. Ventas", 1, "cap5"),
        parrafo(
            f"En {ruta('Ventas')} vive el libro de ventas del mes que tengas seleccionado en "
            "la barra superior. Arriba ves el resumen por tipo de documento y abajo el "
            "detalle de cada uno."
        ),

        titulo("5.1 Registrar una venta", 2, "cap5-1"),
        parrafo(f"Pulsa {ruta('Registrar documento')}. Los campos importantes:"),
        tabla(
            ["Campo", "Cómo se llena"],
            [
                ["Tipo de documento",
                 "El tipo del SII: 33 Factura Electrónica, 39 Boleta Electrónica, "
                 "34 Factura Exenta, 61 Nota de Crédito… La lista completa está en "
                 f"{enlace('§21.1', 'anexo1')}."],
                ["Folio", "El número del documento."],
                ["Fecha emisión", "La fecha que dice el documento."],
                ["Fecha vencimiento",
                 "Opcional. Si la pones, el documento aparecerá en «Vencimientos próximos» "
                 "del panel de inicio."],
                ["Período tributario",
                 "El mes en que <b>declaras</b> el documento en el F29. Normalmente coincide "
                 "con la emisión; cámbialo solo si estás regularizando un documento atrasado."],
                ["Forma de ingreso",
                 "<b>Ingreso el NETO</b> para facturas (escribes el neto y el sistema calcula "
                 "el IVA). <b>Ingreso el TOTAL con IVA incluido</b> para boletas (escribes lo "
                 "que dice la boleta y el sistema despeja neto e IVA)."],
                ["RUT y razón social",
                 "Si el RUT ya existe, el nombre se completa solo. Si es nuevo, se crea la "
                 "ficha del cliente automáticamente. El RUT se valida mientras escribes."],
            ],
            [36 * mm, 135 * mm],
        ),
        parrafo(
            "El total se recalcula en pantalla a medida que escribes, así que puedes "
            "compararlo con el documento antes de guardar."
        ),

        titulo("5.2 El asiento que se genera", 2, "cap5-2"),
        parrafo(
            "Con la casilla <b>Generar el asiento contable</b> marcada (viene marcada), al "
            "guardar se crea el asiento cuadrado:"
        ),
        tabla(
            ["Cuenta", "Debe", "Haber"],
            [
                ["1.1.02.001 Clientes Nacionales <i>(el total con IVA)</i>", "✓", ""],
                ["4.1.01.001 Ventas Afectas <i>(el neto)</i>", "", "✓"],
                ["4.1.01.002 Ventas Exentas <i>(la parte exenta)</i>", "", "✓"],
                ["2.1.03.001 IVA Débito Fiscal <i>(el IVA)</i>", "", "✓"],
            ],
            [131 * mm, 20 * mm, 20 * mm],
        ),
        parrafo(
            "Si la venta fue <b>al contado</b>, despliega <b>Imputación contable</b> y elige "
            "«Caja» o «Banco» como contrapartida en lugar de Clientes. Ahí mismo puedes "
            "cambiar la cuenta de ingreso y asignar un centro de costo."
        ),

        titulo("5.3 Notas de crédito", 2, "cap5-3"),
        parrafo(
            "Registra los montos <b>en positivo</b>, como aparecen en la nota, y elige el "
            "tipo 61. Completa la sección <b>Referencia</b> con el documento que estás "
            "anulando o corrigiendo."
        ),
        parrafo(
            "El sistema se encarga del resto: resta el documento en el libro de ventas, lo "
            "informa en los códigos 509 y 510 del F29, e <b>invierte el asiento contable</b> "
            "(abona Clientes y carga Ventas)."
        ),

        titulo("5.4 Anular un documento", 2, "cap5-4"),
        parrafo(
            "El botón <b>Anular</b> de cada fila marca el documento como anulado, lo saca de "
            "los libros de IVA y <b>elimina su asiento contable</b>. Úsalo cuando registraste "
            "algo mal; para anular una venta real ante el SII, lo correcto es emitir una nota "
            f"de crédito ({enlace('§5.3', 'cap5-3')})."
        ),

        titulo("5.5 Exportar el libro", 2, "cap5-5"),
        vinetas([
            "<b>Excel</b> — el detalle más una hoja de resumen por tipo de documento.",
            "<b>CSV formato SII</b> — columnas en el orden del libro electrónico.",
            "<b>PDF</b> — para imprimir o archivar.",
        ]),
    ]


def cap_compras():
    return [
        PageBreak(),
        titulo("6. Compras", 1, "cap6"),
        parrafo(
            f"{ruta('Compras')} funciona igual que Ventas, con un campo adicional que decide "
            "el destino del IVA."
        ),

        titulo("6.1 El tipo de compra", 2, "cap6-1"),
        parrafo(
            "Es la clasificación que exige el Registro de Compras del SII, y determina si el "
            "IVA de esa factura llega o no a tu crédito fiscal:"
        ),
        tabla(
            ["Tipo de compra", "Qué hace con el IVA", "Cuándo usarlo"],
            [
                ["<b>Del giro</b>", f"Crédito fiscal normal ({cta('1.1.04.001')}). "
                                    "Códigos 519 y 520 del F29.",
                 "La opción habitual: insumos, servicios, mercadería."],
                ["<b>Activo fijo</b>", f"Crédito fiscal de activo fijo ({cta('1.1.04.002')}). "
                                       "Códigos 524 y 525.",
                 "Compras de bienes que se deprecian. El neto va a la cuenta de activo fijo."],
                ["<b>Supermercado</b>", "Crédito fiscal, informado aparte en los códigos "
                                        "553 y 554.",
                 "Compras en supermercados y comercios similares, que el SII exige declarar "
                 "por separado."],
                ["<b>IVA uso común</b>", "Crédito sujeto al factor de proporcionalidad.",
                 "Cuando la empresa tiene ventas afectas y exentas, y la compra sirve a "
                 "ambas."],
                ["<b>IVA no recuperable</b>", f"El IVA va a gasto ({cta('5.3.01.007')}), "
                                              "no a crédito.",
                 "Automóviles y gastos sin relación con el giro."],
            ],
            [30 * mm, 62 * mm, 79 * mm],
        ),

        titulo("6.2 El asiento que se genera", 2, "cap6-2"),
        tabla(
            ["Cuenta", "Debe", "Haber"],
            [
                ["5.1.01.005 Compras del Giro <i>(el neto)</i>", "✓", ""],
                ["1.1.04.001 IVA Crédito Fiscal <i>(el IVA)</i>", "✓", ""],
                ["2.1.02.001 Proveedores Nacionales <i>(el total)</i>", "", "✓"],
            ],
            [131 * mm, 20 * mm, 20 * mm],
        ),
        parrafo(
            "Si clasificaste la compra como <b>Activo fijo</b>, el neto va a la cuenta de "
            "activo fijo y el IVA a la cuenta de crédito fiscal de activo fijo. Para "
            "cualquier otro destino — un gasto específico, por ejemplo — despliega "
            "<b>Imputación contable</b> y elige la cuenta que corresponda."
        ),
        aviso(
            f"Registrar la compra en {ruta('Compras')} <b>no</b> crea la ficha del activo "
            f"fijo. Si compraste un bien depreciable, regístralo también en "
            f"{ruta('Activo fijo')} para que el sistema calcule su depreciación. Ver "
            f"{enlace('capítulo 12', 'cap12')}."
        ),

        titulo("6.3 Facturas de compra y cambio de sujeto", 2, "cap6-3"),
        parrafo(
            "En operaciones con cambio de sujeto (tipos 45 y 46) eres tú quien retiene el IVA "
            "al proveedor y lo entera al Fisco. Anota el monto en el campo <b>Retención</b>: "
            f"se abona a {cta('2.1.03.008')} «Retención Cambio de Sujeto» y aparece en el F29."
        ),
    ]


def cap_honorarios():
    tasas = ", ".join(f"<b>{a}</b>: {t * 100:.2f}%" for a, t in sorted(RETENCION_HONORARIOS.items())
                      if a >= 2023)
    return [
        PageBreak(),
        titulo("7. Boletas de honorarios", 1, "cap7"),
        parrafo(
            f"{ruta('Honorarios')} registra las boletas de profesionales independientes. "
            "Hay dos casos, y conviene no confundirlos."
        ),

        titulo("7.1 Boleta recibida", 2, "cap7-1"),
        parrafo(
            "Un profesional te presta un servicio y te emite su boleta. <b>Tú retienes</b> "
            "el impuesto y lo enteras al SII en el F29 del mes siguiente."
        ),
        parrafo(
            f"Con un bruto de $500.000 y tasa 14,5%, el sistema calcula retención $72.500 y "
            "líquido $427.500, y genera:"
        ),
        tabla(
            ["Cuenta", "Debe", "Haber"],
            [
                ["5.2.01.008 Honorarios Profesionales", "500.000", ""],
                ["2.1.03.004 Retención Honorarios 2ª Categoría", "", "72.500"],
                ["2.1.02.005 Honorarios por Pagar", "", "427.500"],
            ],
            [111 * mm, 30 * mm, 30 * mm],
        ),
        parrafo(
            "La retención aparece en el <b>código 151</b> del F29 y la pagas junto con el "
            "IVA. El líquido queda como deuda hasta que le pagues al profesional."
        ),

        titulo("7.2 Boleta emitida", 2, "cap7-2"),
        parrafo(
            "Es la boleta que emite la propia empresa o su dueño como contribuyente de "
            "segunda categoría. Aquí <b>te retienen a ti</b>: la retención se guarda en "
            f"{cta('1.1.04.007')} y se imputa a tu impuesto anual."
        ),

        titulo("7.3 La tasa de retención", 2, "cap7-3"),
        parrafo(
            f"La Ley 21.133 subió la retención gradualmente. El sistema aplica sola la tasa "
            f"del año de la boleta: {tasas}. Puedes cambiarla en el formulario si necesitas "
            "registrar una boleta antigua."
        ),
    ]


def cap_comprobantes():
    return [
        PageBreak(),
        titulo("8. Comprobantes manuales", 1, "cap8"),
        parrafo(
            f"En {ruta('Contabilidad → Comprobantes')} registras todo lo que no es un "
            "documento tributario: pagos, cobros, aportes de capital, provisiones, ajustes, "
            "traspasos entre cuentas."
        ),

        titulo("8.1 Los tipos de comprobante", 2, "cap8-1"),
        tabla(
            ["Tipo", "Para qué"],
            [
                ["<b>Ingreso</b>", "Entradas de dinero: cobros a clientes, aportes."],
                ["<b>Egreso</b>", "Salidas de dinero: pagos a proveedores, gastos."],
                ["<b>Traspaso</b>", "Movimientos que no involucran caja: provisiones, "
                                    "reclasificaciones, centralizaciones."],
                ["<b>Apertura</b>", "Saldos iniciales al empezar a usar el sistema."],
                ["<b>Cierre</b>", "Lo genera el sistema al cerrar el ejercicio."],
                ["<b>Ajuste</b>", "Correcciones de auditoría o de cierre."],
            ],
            [26 * mm, 145 * mm],
        ),
        parrafo(
            "Cada tipo lleva su propia numeración correlativa por año. Un folio como "
            "<b>T-2025-00014</b> se lee: Traspaso, año 2025, número 14."
        ),

        titulo("8.2 Cargar el asiento", 2, "cap8-2"),
        parrafo(
            "El formulario parte con cuatro líneas y agregas las que necesites. En cada una "
            "eliges la cuenta y escribes el monto en el <b>debe</b> o en el <b>haber</b> — "
            "nunca en ambos: al escribir en uno, el otro se limpia solo."
        ),
        parrafo(
            "Al pie de la tabla se van sumando los totales y la <b>diferencia</b>. "
            "<b>El botón de guardar permanece bloqueado mientras el asiento no cuadre</b>, "
            "así que es imposible dejar la contabilidad descuadrada por descuido."
        ),
        parrafo("Ejemplo — cobro de una factura de $1.190.000 por transferencia:"),
        tabla(
            ["Cuenta", "Debe", "Haber"],
            [
                ["1.1.01.003 Banco Cuenta Corriente", "1.190.000", ""],
                ["1.1.02.001 Clientes Nacionales <i>(auxiliar: el cliente)</i>", "", "1.190.000"],
            ],
            [111 * mm, 30 * mm, 30 * mm],
        ),

        titulo("8.3 Anular un comprobante", 2, "cap8-3"),
        parrafo(
            "Los comprobantes no se borran: se <b>anulan</b>, indicando el motivo. El asiento "
            "queda en el sistema con estado «Anulado» y deja de considerarse en libros, "
            "balances e informes. Así la historia queda trazable."
        ),
        aviso(
            "Los asientos generados automáticamente desde compras, ventas, honorarios, "
            "remuneraciones o depreciación llevan la marca de su <b>origen</b>. No los "
            "edites a mano: corrige el documento que los originó y el sistema los regenera."
        ),
    ]


def cap_libros():
    return [
        PageBreak(),
        titulo("9. Libros contables", 1, "cap9"),

        titulo("9.1 Libro Diario", 2, "cap9-1"),
        parrafo(
            f"{ruta('Contabilidad → Libro Diario')} muestra todos los asientos del mes en "
            "orden cronológico, con su detalle línea por línea. Es el libro que registra los "
            "hechos tal como fueron ocurriendo."
        ),

        titulo("9.2 Libro Mayor", 2, "cap9-2"),
        parrafo(
            f"{ruta('Contabilidad → Libro Mayor')} toma <b>una cuenta</b> y muestra todos sus "
            "movimientos con el <b>saldo corrido</b>: el saldo anterior arriba, cada "
            "movimiento y cómo va quedando el saldo después de cada uno."
        ),
        parrafo(
            "Es la herramienta para responder «¿por qué esta cuenta quedó con este saldo?». "
            "Cada folio es un enlace al comprobante completo."
        ),

        titulo("9.3 Balance de Comprobación y Saldos (8 columnas)", 2, "cap9-3"),
        parrafo(
            f"{ruta('Contabilidad → Balance 8 columnas')} es la radiografía de la "
            "contabilidad en una sola hoja. Cada cuenta con movimiento aparece con cuatro "
            "pares de columnas:"
        ),
        tabla(
            ["Par de columnas", "Qué muestra"],
            [
                ["<b>Sumas</b> (Debe / Haber)",
                 "Todo lo cargado y abonado en la cuenta desde el 1 de enero."],
                ["<b>Saldos</b> (Deudor / Acreedor)",
                 "La diferencia entre ambas sumas, puesta en la columna que corresponda."],
                ["<b>Inventario</b> (Activo / Pasivo)",
                 "Los saldos de las cuentas de balance. Es tu situación patrimonial."],
                ["<b>Resultado</b> (Pérdida / Ganancia)",
                 "Los saldos de las cuentas de resultado. Es tu resultado del período."],
            ],
            [42 * mm, 129 * mm],
        ),
        parrafo(
            "Al pie aparece el resultado del ejercicio y la fila <b>Sumas iguales</b>: las "
            "cuatro columnas finales deben quedar pareadas. Si no cuadran, hay una cuenta "
            "mal clasificada."
        ),
    ]


def cap_informes():
    return [
        PageBreak(),
        titulo("10. Informes financieros", 1, "cap10"),

        titulo("10.1 Estado de Resultados", 2, "cap10-1"),
        parrafo(
            f"{ruta('Informes → Estado de Resultados')} muestra si ganaste o perdiste en el "
            "rango de meses que elijas, con los márgenes intermedios que importan:"
        ),
        tabla(
            ["Línea", "Cómo se calcula", "Qué te dice"],
            [
                ["Ingresos de explotación", "Cuentas 4.1", "Cuánto vendiste."],
                ["(−) Costos de explotación", "Cuentas 5.1", "Cuánto te costó lo vendido."],
                ["<b>= Margen bruto</b>", "", "Cuánto deja el negocio antes de la estructura."],
                ["(−) Gastos de adm. y ventas", "Cuentas 5.2",
                 "Lo que cuesta mantener la empresa funcionando."],
                ["<b>= Resultado operacional</b>", "",
                 "Si el negocio en sí es rentable. Es la línea clave."],
                ["(+) Otros ingresos", "Cuentas 4.2", "Ingresos ajenos al giro."],
                ["(−) Gastos fuera de explotación", "Cuentas 5.3",
                 "Intereses, diferencias de cambio, multas."],
                ["<b>= Resultado antes de impuesto</b>", "",
                 "La base desde la que parte el Formulario 22."],
                ["(−) Impuesto a la renta", "Cuentas 5.4", ""],
                ["<b>= Resultado del ejercicio</b>", "", "Lo que finalmente ganaste o perdiste."],
            ],
            [50 * mm, 34 * mm, 87 * mm],
        ),

        titulo("10.2 Estado de Situación Financiera", 2, "cap10-2"),
        parrafo(
            f"{ruta('Informes → Situación Financiera')} es el balance clásico: qué tiene la "
            "empresa y con qué lo financió, a una fecha determinada."
        ),
        vinetas([
            "<b>Activo corriente</b> — lo que se convierte en dinero dentro de un año.",
            "<b>Activo no corriente</b> — activo fijo, intangibles e inversiones permanentes.",
            "<b>Pasivo corriente</b> — lo que hay que pagar dentro de un año.",
            "<b>Pasivo no corriente</b> — deuda de largo plazo.",
            "<b>Patrimonio</b> — capital, reservas, resultados acumulados y el resultado "
            "del ejercicio en curso.",
        ]),
        parrafo(
            "Los dos totales tienen que ser idénticos. Si no lo son, el informe muestra un "
            "aviso con el monto del descuadre."
        ),

        titulo("10.3 Análisis de cuentas", 2, "cap10-3"),
        parrafo(
            f"{ruta('Informes → Análisis de cuentas')} abre una cuenta con auxiliar y muestra "
            "el saldo <b>por cliente o proveedor</b>. Es como se responde «¿quién me debe?» "
            f"y «¿a quién le debo?». Solo aparecen las cuentas marcadas con "
            f"{enlace('«Exige cliente/proveedor»', 'cap4-2')}."
        ),
    ]


def cap_remuneraciones():
    tramos = []
    for desde, hasta, factor, rebaja in TABLA_IMPUESTO_UNICO_UTM:
        rango = f"Más de {desde} y hasta {hasta} UTM" if hasta else f"Más de {desde} UTM"
        if desde == 0:
            rango = f"Hasta {hasta} UTM"
        tramos.append([rango, f"{factor * 100:.1f}%", f"{rebaja} UTM"])

    return [
        PageBreak(),
        titulo("11. Remuneraciones", 1, "cap11"),

        titulo("11.1 Ficha del trabajador", 2, "cap11-1"),
        parrafo(
            f"En {ruta('Remuneraciones → Trabajadores')} creas la ficha. Estos campos "
            "cambian el resultado del cálculo:"
        ),
        tabla(
            ["Campo", "Efecto en la liquidación"],
            [
                ["<b>Tipo de contrato</b>",
                 f"Define el seguro de cesantía. Indefinido: "
                 f"{TASAS_AFC['INDEFINIDO'][0] * 100:.1f}% del trabajador y "
                 f"{TASAS_AFC['INDEFINIDO'][1] * 100:.1f}% del empleador. Plazo fijo: "
                 f"{TASAS_AFC['PLAZO_FIJO'][1] * 100:.1f}%, todo de cargo del empleador."],
                ["<b>Sueldo base</b>", "El sueldo mensual por jornada completa. Se prorratea "
                                       "si el trabajador no cumple los 30 días."],
                ["<b>Gratificación Art. 50</b>",
                 "Agrega el 25% de lo devengado, con tope de 4,75 ingresos mínimos al año "
                 "(el tope mensual sale de dividir por 12)."],
                ["<b>AFP</b>", "Determina la tasa de cotización: 10% obligatorio más la "
                               "comisión de la administradora."],
                ["<b>Salud</b>", f"Fonasa descuenta el {TASA_SALUD_LEGAL * 100:.0f}% legal. "
                                 "Con Isapre, si el plan pactado en UF supera ese 7%, la "
                                 "diferencia se descuenta como «salud adicional»."],
                ["<b>Jubilado</b>", "No cotiza en AFP y el empleador no paga SIS."],
                ["<b>Cargas familiares y tramo</b>",
                 "Suman asignación familiar, que es un haber no imponible ni tributable."],
                ["<b>Colación y movilización</b>",
                 "Haberes no imponibles fijos, que se prorratean por días trabajados."],
            ],
            [42 * mm, 129 * mm],
        ),

        titulo("11.2 Calcular las liquidaciones", 2, "cap11-2"),
        parrafo(f"En {ruta('Remuneraciones → Liquidaciones')} tienes dos caminos:"),
        vinetas([
            "<b>Calcular todos con datos base</b> — usa el sueldo y las asignaciones fijas de "
            "cada ficha, con 30 días trabajados. Es el mes normal: un clic y listo.",
            "<b>Calcular liquidación individual</b> — para quien tuvo horas extra, bonos, "
            "comisiones, anticipos o trabajó menos días.",
        ]),
        parrafo(
            "Recalcular a una persona reemplaza su liquidación anterior del mismo mes, así "
            "que puedes corregir cuantas veces necesites."
        ),

        titulo("11.3 Cómo se calcula", 2, "cap11-3"),
        numerada([
            "<b>Total imponible</b> = sueldo base prorrateado + gratificación + horas extra "
            "+ bonos + comisiones.",
            f"<b>Topes</b> — para AFP y salud se considera hasta {TOPE_IMPONIBLE_AFP_UF} UF; "
            f"para el seguro de cesantía hasta {TOPE_IMPONIBLE_AFC_UF} UF.",
            "<b>Descuentos del trabajador</b> = AFP (según su administradora) + salud (7% o "
            "el plan Isapre) + seguro de cesantía.",
            "<b>Base tributable</b> = total imponible − esos descuentos previsionales.",
            "<b>Impuesto Único</b> — la base se divide por la UTM del mes y se busca el tramo "
            f"en la tabla ({enlace('§11.4', 'cap11-4')}).",
            "<b>Líquido</b> = total haberes − total descuentos.",
            f"<b>Costo empresa</b> = total haberes + SIS ({TASA_SIS_EMPLEADOR * 100:.2f}%) "
            "+ seguro de cesantía del empleador + mutual.",
        ]),

        titulo("11.4 Tabla del Impuesto Único de Segunda Categoría", 2, "cap11-4"),
        parrafo(
            "Se aplica sobre la base tributable expresada en UTM. El impuesto es "
            "<b>base × factor − rebaja</b>, y la rebaja está en UTM."
        ),
        tabla(["Tramo (en UTM)", "Factor", "Rebaja"], tramos,
              [95 * mm, 38 * mm, 38 * mm]),
        parrafo(
            "Por eso el impuesto es progresivo y no da saltos: quien gana un peso más que el "
            "límite de un tramo no paga bruscamente más."
        ),

        titulo("11.5 Libro de remuneraciones y centralización", 2, "cap11-5"),
        parrafo(
            f"{ruta('Remuneraciones → Libro de remuneraciones')} reúne a todos los "
            "trabajadores del mes con sus haberes, descuentos, líquido y costo empresa. "
            "Se exporta a Excel, CSV y PDF."
        ),
        parrafo(
            f"El botón {ruta('Centralizar en contabilidad')} genera <b>un solo asiento</b> "
            "con los totales del mes: sueldos, gratificaciones, leyes sociales y mutual al "
            "debe; cotizaciones, impuesto único y líquido por pagar al haber. El impuesto "
            "único retenido alimenta el código 48 del F29."
        ),

        titulo("11.6 Finiquitos", 2, "cap11-6"),
        parrafo(
            f"{ruta('Remuneraciones → Finiquitos')} calcula, de forma referencial, la "
            "indemnización por años de servicio (un mes por año, con tope de 11 y "
            "considerando año completo la fracción superior a 6 meses), la indemnización "
            "sustitutiva del aviso previo y el feriado proporcional."
        ),
        aviso(
            "El finiquito es un cálculo de apoyo: no incluye las remuneraciones pendientes "
            "del mes ni bonos proporcionales. Revísalo con detención antes de firmar."
        ),
    ]


def cap_activo_fijo():
    return [
        PageBreak(),
        titulo("12. Activo fijo", 1, "cap12"),
        parrafo(
            "Los bienes que duran más de un año no se llevan a gasto de una vez: se "
            "<b>deprecian</b>, repartiendo su costo a lo largo de su vida útil. "
            f"{ruta('Activo fijo')} lleva ese control."
        ),

        titulo("12.1 Registrar un bien", 2, "cap12-1"),
        tabla(
            ["Campo", "Qué poner"],
            [
                ["Código", "Un identificador tuyo: AF-001, COMP-03, VEH-01."],
                ["Fecha de adquisición", "La de la factura. La depreciación empieza el "
                                         "<b>mes siguiente</b>."],
                ["Valor de adquisición", "El <b>neto</b> de la factura, sin IVA, más todo lo "
                                         "necesario para dejar el bien operativo (flete, "
                                         "instalación)."],
                ["Valor residual", "Lo que esperas que valga al final de su vida útil. "
                                   "Normalmente 0 o $1."],
                ["Vida útil (meses)", "Según la tabla del SII. El campo Categoría te sugiere "
                                      f"las oficiales ({enlace('§12.2', 'cap12-2')})."],
                ["Depreciación acelerada", "Divide la vida útil por 3, con mínimo 12 meses. "
                                           "Adelanta el gasto y reduce el impuesto de los "
                                           "primeros años."],
            ],
            [40 * mm, 131 * mm],
        ),

        titulo("12.2 Vidas útiles según el SII", 2, "cap12-2"),
        parrafo("Resolución Exenta N°43 de 2002, vidas útiles normales:"),
        tabla(
            ["Bien", "Años", "Meses"],
            [[nombre, str(anios), str(anios * 12)] for nombre, anios in VIDAS_UTILES_SII],
            [115 * mm, 28 * mm, 28 * mm],
        ),

        titulo("12.3 Contabilizar la depreciación", 2, "cap12-3"),
        parrafo(
            f"Una vez al mes, pulsa {ruta('Contabilizar depreciación del mes')}. El sistema "
            "calcula la cuota de cada activo vigente y genera un solo asiento:"
        ),
        tabla(
            ["Cuenta", "Debe", "Haber"],
            [
                ["5.2.03.001 Depreciación del Ejercicio", "✓", ""],
                ["1.2.02.xxx Dep. Acumulada <i>(la del bien)</i>", "", "✓"],
            ],
            [131 * mm, 20 * mm, 20 * mm],
        ),
        parrafo(
            "Puedes repetir la operación las veces que quieras: el sistema reemplaza el "
            "asiento del mes en vez de duplicarlo. <b>Ver tabla</b> muestra el calendario "
            "completo de un activo, mes a mes, hasta el final de su vida útil."
        ),

        titulo("12.4 Vender o dar de baja", 2, "cap12-4"),
        parrafo(
            "Pulsa <b>Baja</b>, indica la fecha y el valor de venta (0 si es desecho). "
            "El sistema elimina el costo y la depreciación acumulada, y calcula el resultado "
            "contra el valor libro:"
        ),
        vinetas([
            f"Vendes <b>sobre</b> el valor libro → utilidad, que se abona a {cta('4.2.01.002')}.",
            f"Vendes <b>bajo</b> el valor libro → pérdida, que se carga a {cta('5.3.01.002')}.",
        ]),
        aviso(
            "Dar de baja el activo fijo no reemplaza a la factura de venta. Si vendiste el "
            f"bien, registra además el documento en {ruta('Ventas')} para que el IVA débito "
            "quede declarado."
        ),
    ]


def cap_f29():
    codigos = [
        ["110 / 111", "Boletas: cantidad y débito de IVA"],
        ["503 / 502", "Facturas emitidas: cantidad y débito de IVA"],
        ["509 / 510", "Notas de crédito emitidas: cantidad y débito que rebajan"],
        ["512 / 513", "Notas de débito emitidas: cantidad y débito que agregan"],
        ["142", "Ventas y servicios exentos o no gravados"],
        ["585", "Exportaciones, monto neto"],
        ["563", "Monto neto de ventas del giro — <b>es la base de los PPM</b>"],
        ["<b>537</b>", "<b>TOTAL DÉBITOS</b> — el IVA que cobraste"],
        ["519 / 520", "Facturas recibidas del giro: cantidad y crédito de IVA"],
        ["524 / 525", "Facturas de activo fijo: cantidad y crédito"],
        ["527 / 528", "Notas de crédito recibidas: cantidad y crédito que rebajan"],
        ["531 / 532", "Notas de débito recibidas: cantidad y crédito que agregan"],
        ["534 / 535", "Importaciones (DIN): cantidad y crédito"],
        ["553 / 554", "Compras en supermercados: cantidad y crédito"],
        ["564", "Monto neto de compras y servicios recibidos"],
        ["504", "Remanente de crédito fiscal del mes anterior"],
        ["<b>538</b>", "<b>TOTAL CRÉDITOS</b> — el IVA que pagaste"],
        ["<b>89</b>", "<b>IVA determinado a pagar</b> (cuando 537 supera a 538 + 504)"],
        ["<b>77</b>", "<b>Remanente para el mes siguiente</b> (cuando ocurre lo contrario)"],
        ["151 / 152", "Retención de honorarios y monto bruto pagado"],
        ["48", "Retención del Impuesto Único a los Trabajadores"],
        ["39", "Retención por cambio de sujeto"],
        ["115 / 62", "Tasa de PPM aplicada y PPM neto determinado"],
        ["66", "Crédito por gastos de capacitación (SENCE)"],
        ["<b>547</b>", "<b>TOTAL DETERMINADO</b>"],
        ["<b>91</b>", "<b>TOTAL A PAGAR DENTRO DEL PLAZO LEGAL</b>"],
    ]
    return [
        PageBreak(),
        titulo("13. Formulario 29 (IVA mensual)", 1, "cap13"),
        parrafo(
            f"{ruta('Formulario 29')} calcula una <b>propuesta</b> del formulario a partir de "
            "todo lo que registraste en el mes: libros de compras y ventas, honorarios y "
            "remuneraciones."
        ),
        aviso(
            "Esta propuesta <b>no se envía al SII</b>. Es un documento de trabajo para que "
            "traspases los valores al formulario oficial. Verifica siempre los códigos contra "
            "el formulario vigente del año antes de declarar."
        ),

        titulo("13.1 Los cuatro indicadores de arriba", 2, "cap13-1"),
        vinetas([
            "<b>IVA determinado</b> — débitos menos créditos menos remanente anterior.",
            "<b>Remanente anterior</b> — lo que sobró del mes pasado (código 504).",
            "<b>Remanente siguiente</b> — lo que sobra este mes y pasará al próximo (código 77).",
            "<b>Total a pagar</b> — IVA más PPM más retenciones (código 91).",
        ]),

        titulo("13.2 Los códigos que calcula", 2, "cap13-2"),
        tabla(["Código", "Concepto"], codigos, [26 * mm, 145 * mm]),

        titulo("13.3 Ajustes antes de declarar", 2, "cap13-3"),
        parrafo("Los campos superiores permiten sobrescribir tres cosas y recalcular:"),
        vinetas([
            "<b>Remanente mes anterior</b> — si lo dejas vacío, toma el del F29 guardado el "
            "mes pasado. Escríbelo solo si estás partiendo a mitad de año.",
            "<b>Tasa PPM</b> — usa la de la ficha de la empresa salvo que indiques otra.",
            "<b>Crédito SENCE</b> — rebaja el PPM a pagar.",
        ]),

        titulo("13.4 Guardar el F29", 2, "cap13-4"),
        parrafo(
            "Este paso es <b>importante y fácil de olvidar</b>. Al pulsar "
            f"{ruta('Guardar F29')}, el remanente del código 77 queda registrado y el mes "
            "siguiente aparecerá solo en el código 504."
        ),
        parrafo(
            "Es lo que encadena los períodos: si no guardas, el mes siguiente partirá sin "
            "remanente y el IVA a pagar saldrá más alto de lo que corresponde."
        ),

        titulo("13.5 Exportar", 2, "cap13-5"),
        parrafo(
            "PDF con los códigos agrupados por sección y las advertencias del período, Excel "
            "con hoja de resumen, o CSV. El PDF es el más cómodo para tenerlo al lado "
            "mientras llenas el formulario en el sitio del SII "
            f"({externo('www.sii.cl', 'https://www.sii.cl')})."
        ),
    ]


def cap_f22():
    return [
        PageBreak(),
        titulo("14. Formulario 22 (Renta anual)", 1, "cap14"),
        parrafo(
            f"{ruta('Formulario 22')} parte del resultado que arroja tu balance y le aplica "
            "los ajustes tributarios para llegar a la <b>Renta Líquida Imponible</b> (RLI), "
            "que es la base sobre la que se calcula el impuesto."
        ),

        titulo("14.1 Cómo se llega a la RLI", 2, "cap14-1"),
        tabla(
            ["Paso", "De dónde sale"],
            [
                ["Resultado según balance", "Lo calcula el sistema desde tu contabilidad."],
                ["(+) Agregados", "<b>Lo escribes tú.</b> Gastos que la contabilidad aceptó "
                                  "pero la Ley de la Renta no: multas fiscales, gastos "
                                  "personales de los socios, desembolsos sin respaldo."],
                ["(−) Deducciones", "<b>Lo escribes tú.</b> Ingresos que la contabilidad "
                                    "registró pero no pagan impuesto: ingresos no renta y "
                                    "rentas exentas."],
                ["(−) Pérdida de arrastre", "<b>Lo escribes tú.</b> Pérdidas tributarias de "
                                            "ejercicios anteriores."],
                ["<b>= Renta Líquida Imponible</b>", "El resultado de la operación."],
            ],
            [50 * mm, 121 * mm],
        ),
        parrafo(
            "Los tres ajustes son criterio del contador: dependen del análisis de cada "
            "cuenta, por eso el sistema no los inventa."
        ),

        titulo("14.2 El impuesto y el saldo", 2, "cap14-2"),
        parrafo(
            "Sobre la RLI se aplica la tasa del régimen (25% en Pro Pyme General, 27% en "
            "Semi Integrado). De ahí se restan los créditos y los <b>PPM pagados durante el "
            "año</b>, que tú informas. El resultado es el saldo a pagar o la devolución a "
            "solicitar."
        ),
        parrafo(
            "Si la RLI resulta negativa, el sistema muestra la <b>pérdida tributaria</b> que "
            "arrastrarás al ejercicio siguiente."
        ),
        aviso(
            "La propuesta de F22 no incluye la corrección monetaria ni la determinación de "
            "los registros empresariales (RAI, DDAN, REX, SAC), que deben analizarse aparte. "
            "En el régimen 14 D N°8 la empresa está liberada del impuesto: la base se asigna "
            "a los dueños."
        ),
    ]


def cap_cierres():
    return [
        PageBreak(),
        titulo("15. Períodos, cierres y conciliación", 1, "cap15"),

        titulo("15.1 Cerrar un mes", 2, "cap15-1"),
        parrafo(
            f"En {ruta('Contabilidad → Períodos')} cierras cada mes una vez declarado. Un mes "
            "cerrado <b>no admite asientos nuevos ni modificaciones</b>: es la garantía de "
            "que lo que declaraste sigue siendo lo que dice tu contabilidad."
        ),
        parrafo("Si necesitas corregir algo, reabre el mes, corrige y vuelve a cerrarlo."),

        titulo("15.2 Cerrar el ejercicio", 2, "cap15-2"),
        parrafo(
            "Al terminar el año, el botón <b>Generar asiento de cierre</b> traspasa el saldo "
            f"de todas las cuentas de resultado a {cta('3.1.03.003')} «Resultado del "
            "Ejercicio». El estado de resultados queda en cero al 31 de diciembre y el "
            "balance conserva la utilidad o pérdida en el patrimonio."
        ),
        aviso(
            "Crea un respaldo <b>antes</b> de generar el cierre. Es una operación que toca "
            "todas las cuentas de resultado del año."
        ),

        titulo("15.3 Conciliación bancaria", 2, "cap15-3"),
        parrafo(
            f"{ruta('Contabilidad → Conciliación bancaria')} lista los movimientos del mes de "
            "una cuenta de banco. Vas marcando los que ya aparecen en la cartola y guardas."
        ),
        parrafo(
            "Lo que queda sin marcar es la diferencia entre tus libros y el banco: cheques "
            "girados que aún no se cobran, depósitos en tránsito, cargos que el banco hizo y "
            "tú no registraste."
        ),
        parrafo(
            f"Para que una cuenta aparezca aquí debe estar marcada como <b>«Es cuenta "
            f"bancaria»</b> en el plan de cuentas ({enlace('§4.2', 'cap4-2')})."
        ),
    ]


def cap_configuracion():
    filas_defecto = [
        [cta(codigo), descripcion, clave]
        for clave, (codigo, descripcion) in sorted(CUENTAS_DEFECTO.items(), key=lambda x: x[1][0])
    ]
    return [
        PageBreak(),
        titulo("16. Rutinas de trabajo", 1, "cap16"),

        titulo("16.1 Cada mes", 2, "cap16-1"),
        parrafo("Este es el orden que evita tener que rehacer trabajo:"),
        numerada([
            f"Selecciona el <b>período</b> correcto en la barra superior.",
            f"Registra todas las <b>ventas</b> del mes ({enlace('cap. 5', 'cap5')}).",
            f"Registra todas las <b>compras</b> ({enlace('cap. 6', 'cap6')}).",
            f"Registra las <b>boletas de honorarios</b> ({enlace('cap. 7', 'cap7')}).",
            f"Calcula las <b>liquidaciones</b> y <b>centraliza</b> "
            f"({enlace('cap. 11', 'cap11')}).",
            f"Contabiliza la <b>depreciación</b> del activo fijo ({enlace('cap. 12', 'cap12')}).",
            "Registra pagos, cobros y ajustes con comprobantes manuales.",
            f"Revisa el <b>Balance de 8 columnas</b>: las sumas deben cuadrar "
            f"({enlace('§9.3', 'cap9-3')}).",
            f"Genera la <b>propuesta de F29</b> y <b>guárdala</b> ({enlace('cap. 13', 'cap13')}).",
            "Declara en el sitio del SII usando la propuesta como referencia.",
            f"<b>Cierra el período</b> ({enlace('§15.1', 'cap15-1')}).",
            f"Crea un <b>respaldo</b> ({enlace('§17.4', 'cap17-4')}).",
        ]),

        titulo("16.2 Cada año", 2, "cap16-2"),
        numerada([
            "Verifica que los 12 meses estén cerrados.",
            "Revisa el Estado de Resultados y la Situación Financiera anuales.",
            f"Genera la propuesta de <b>F22</b>, completando agregados, deducciones, pérdida "
            f"de arrastre y PPM pagados ({enlace('cap. 14', 'cap14')}).",
            f"Genera el <b>asiento de cierre del ejercicio</b> ({enlace('§15.2', 'cap15-2')}).",
            "Carga los indicadores del año nuevo y revisa los parámetros previsionales.",
            "Respalda y guarda una copia fuera del computador.",
        ]),

        PageBreak(),
        titulo("17. Configuración del sistema", 1, "cap17"),

        titulo("17.1 Cuentas por defecto", 2, "cap17-1"),
        parrafo(
            f"{ruta('Configuración → Cuentas por defecto')} define qué cuenta usa cada asiento "
            "automático. Vienen configuradas; cámbialas solo si tu forma de trabajar difiere."
        ),
        tabla(
            ["Cuenta", "Se usa para", "Clave interna"],
            filas_defecto, [26 * mm, 100 * mm, 45 * mm],
        ),

        titulo("17.2 Parámetros", 2, "cap17-2"),
        parrafo(f"{ruta('Configuración → Parámetros')} reúne las tasas editables:"),
        vinetas([
            "<b>Tasa mutual</b> — 0,90% básico más la adicional según el riesgo de tu actividad.",
            "<b>Proporcionalidad IVA uso común</b> — el porcentaje del IVA de uso común con "
            "derecho a crédito, cuando tienes ventas afectas y exentas.",
            "<b>Tasas de AFP</b> — 10% obligatorio más la comisión de cada administradora. "
            "Actualízalas cuando la Superintendencia de Pensiones publique cambios.",
        ]),
        parrafo(
            "La misma pantalla muestra, solo como referencia, los topes imponibles, la tabla "
            "del Impuesto Único, los tramos de asignación familiar y las tasas de retención "
            "de honorarios por año."
        ),

        titulo("17.3 Usuarios", 2, "cap17-3"),
        tabla(
            ["Rol", "Qué puede hacer"],
            [
                ["<b>Administrador</b>", "Todo, incluida la gestión de usuarios."],
                ["<b>Contador</b>", "Registrar y consultar; no administra usuarios."],
                ["<b>Consulta</b>", "Solo ver informes."],
            ],
            [34 * mm, 137 * mm],
        ),
        parrafo("Los usuarios son globales: acceden a todas las empresas registradas."),

        titulo("17.4 Respaldos", 2, "cap17-4"),
        parrafo(
            f"{ruta('Configuración → Respaldos')} copia la base completa — todas las empresas "
            "— a la carpeta de respaldos. Hazlo al menos una vez al mes, y siempre antes de "
            "cerrar un ejercicio o restaurar."
        ),
        parrafo(
            "<b>Restaurar</b> reemplaza todos los datos actuales por los del respaldo. Antes "
            "de hacerlo, el sistema guarda automáticamente una copia del estado actual, así "
            "que siempre puedes volver atrás. Después de restaurar, cierra y vuelve a abrir "
            "ContaFlow."
        ),
        aviso(
            "Los respaldos quedan en el mismo computador. Si se echa a perder el disco, se "
            "pierden con él. Copia los respaldos a un pendrive o a la nube."
        ),
    ]


def cap_problemas():
    return [
        PageBreak(),
        titulo("18. Problemas frecuentes", 1, "cap18"),
        tabla(
            ["Lo que ves", "Qué pasa y cómo se resuelve"],
            [
                ["«Registré una venta y no aparece».",
                 "Casi siempre es el <b>período</b> de la barra superior: estás mirando otro "
                 "mes. Revisa también el «Período tributario» con que guardaste el documento."],
                ["«El RUT no es válido».",
                 "El dígito verificador no calza. Revisa los números; el sistema valida con "
                 "módulo 11 y no acepta RUT inventados."],
                ["«El período está cerrado».",
                 f"El mes fue cerrado. Reábrelo en {ruta('Contabilidad → Períodos')}, corrige, "
                 "y vuelve a cerrarlo."],
                ["«El asiento no cuadra».",
                 "El debe y el haber son distintos. El mensaje indica la diferencia exacta; "
                 "revisa los montos de cada línea."],
                ["«La cuenta es de agrupación y no admite movimientos».",
                 f"Elegiste una rama del árbol en vez de una hoja. Usa una cuenta de cuarto "
                 f"nivel ({enlace('§2.3', 'cap2-3')})."],
                ["«La cuenta exige indicar cliente/proveedor».",
                 "Esa cuenta lleva auxiliar obligatorio. Selecciónalo en la columna "
                 "correspondiente de la línea."],
                ["«Faltan los indicadores del mes».",
                 f"No has cargado UF, UTM e ingreso mínimo. Ve a "
                 f"{ruta('Maestros → Indicadores')} ({enlace('§3.3', 'cap3-3')})."],
                ["«Falta configurar la cuenta …».",
                 f"Una cuenta por defecto quedó sin asignar. Revísala en "
                 f"{ruta('Configuración → Cuentas por defecto')}."],
                ["El balance está descuadrado.",
                 "Como el sistema rechaza asientos descuadrados, suele ser una cuenta mal "
                 "clasificada (un gasto imputado a una cuenta de activo, por ejemplo). "
                 "Búscala en el Balance de 8 columnas."],
                ["El IVA a pagar salió más alto de lo esperado.",
                 f"Probablemente no guardaste el F29 del mes anterior, así que el remanente "
                 f"no se arrastró ({enlace('§13.4', 'cap13-4')})."],
                ["Windows advierte al abrir el programa.",
                 "SmartScreen avisa porque el ejecutable no tiene firma digital comercial. "
                 "Elige «Más información» → «Ejecutar de todas formas»."],
                ["Cerré la ventanita azul y el sistema dejó de responder.",
                 "Esa ventana <b>es</b> el sistema. Vuelve a abrir ContaFlow.exe."],
            ],
            [52 * mm, 119 * mm],
        ),
    ]


def cap_glosario():
    return [
        PageBreak(),
        titulo("19. Glosario de siglas", 1, "cap19"),
        tabla(
            ["Sigla", "Significado"],
            [
                ["<b>AFC</b>", "Administradora de Fondos de Cesantía. El seguro de cesantía."],
                ["<b>AFP</b>", "Administradora de Fondos de Pensiones."],
                ["<b>BTE</b>", "Boleta de Terceros Electrónica: boleta de honorarios."],
                ["<b>DTE</b>", "Documento Tributario Electrónico: factura, boleta, nota de "
                               "crédito, guía de despacho."],
                ["<b>F22</b>", "Formulario 22: declaración anual de impuesto a la renta."],
                ["<b>F29</b>", "Formulario 29: declaración mensual de IVA, PPM y retenciones."],
                ["<b>ILA</b>", "Impuesto a bebidas alcohólicas, analcohólicas y similares."],
                ["<b>IMM</b>", "Ingreso Mínimo Mensual."],
                ["<b>IVA</b>", "Impuesto al Valor Agregado, 19% en Chile."],
                ["<b>LIR</b>", "Ley sobre Impuesto a la Renta."],
                ["<b>PPM</b>", "Pago Provisional Mensual: anticipo del impuesto anual."],
                ["<b>RLI</b>", "Renta Líquida Imponible: la base del impuesto de Primera "
                               "Categoría."],
                ["<b>SENCE</b>", "Servicio Nacional de Capacitación y Empleo."],
                ["<b>SII</b>", "Servicio de Impuestos Internos."],
                ["<b>SIS</b>", "Seguro de Invalidez y Sobrevivencia, de cargo del empleador."],
                ["<b>UF</b>", "Unidad de Fomento."],
                ["<b>UTA</b>", "Unidad Tributaria Anual (12 UTM)."],
                ["<b>UTM</b>", "Unidad Tributaria Mensual."],
            ],
            [24 * mm, 147 * mm],
        ),
    ]


def cap_anexos():
    ventas = [[str(c), n] for c, n, v, _co, _a, _s, _e in TIPOS_DTE if v]
    compras = [[str(c), n] for c, n, _v, co, _a, _s, _e in TIPOS_DTE if co]
    return [
        PageBreak(),
        titulo("20. Anexos", 1, "anexos"),

        titulo("20.1 Tipos de documento del SII", 2, "anexo1"),
        parrafo("<b>Documentos de venta</b> (los que emites):"),
        tabla(["Código", "Documento"], ventas, [24 * mm, 147 * mm]),
        parrafo("<b>Documentos de compra</b> (los que recibes):"),
        tabla(["Código", "Documento"], compras, [24 * mm, 147 * mm]),

        titulo("20.2 Enlaces útiles", 2, "anexo2"),
        vinetas([
            f"{externo('Servicio de Impuestos Internos — sii.cl', 'https://www.sii.cl')} — "
            "declaración de F29 y F22, consulta de documentos recibidos.",
            f"{externo('Previred — previred.com', 'https://www.previred.com')} — pago de "
            "cotizaciones previsionales.",
            f"{externo('Dirección del Trabajo — dt.gob.cl', 'https://www.dt.gob.cl')} — "
            "normativa laboral, contratos y finiquitos.",
            f"{externo('Superintendencia de Pensiones — spensiones.cl', 'https://www.spensiones.cl')}"
            " — tasas de AFP vigentes.",
            f"{externo('Banco Central — bcentral.cl', 'https://www.bcentral.cl')} — valores de "
            "UF, UTM, IPC y tipo de cambio.",
        ]),

        Spacer(1, 10),
        tabla(
            ["", ""],
            [[
                "<b>Recuerda</b>",
                "ContaFlow es una herramienta de apoyo. Las propuestas de formularios se "
                "calculan desde tu contabilidad, pero el SII actualiza sus formularios y los "
                "organismos previsionales sus tasas periódicamente. Contrasta siempre antes "
                "de declarar, y respalda tus datos con regularidad.",
            ]],
            [26 * mm, 145 * mm],
        ),
    ]


# ---------------------------------------------------------------------------
# Construcción
# ---------------------------------------------------------------------------


def construir(salida: Path) -> Path:
    faltantes = cuentas_sin_glosario()
    if faltantes:
        raise SystemExit(
            f"Hay {len(faltantes)} cuentas sin descripción en el glosario: {faltantes[:5]}…"
        )

    salida.parent.mkdir(parents=True, exist_ok=True)
    doc = ManualDoc(
        str(salida), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=22 * mm,
        title=f"Manual de usuario · {APP_NAME} {APP_VERSION}",
        author=APP_NAME, subject="Manual de usuario del sistema contable chileno ContaFlow",
    )
    marco = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([
        PageTemplate(id="portada", frames=[marco], onPage=dibujar_portada),
        PageTemplate(id="indice", frames=[marco], onPage=dibujar_pie),
        PageTemplate(id="normal", frames=[marco], onPage=dibujar_pie),
    ])

    elementos: list = []
    elementos += portada()
    elementos += indice()
    elementos += cap_bienvenida()
    elementos += cap_conceptos()
    elementos += cap_puesta_en_marcha()
    elementos += cap_plan_cuentas()
    elementos += cap_ventas()
    elementos += cap_compras()
    elementos += cap_honorarios()
    elementos += cap_comprobantes()
    elementos += cap_libros()
    elementos += cap_informes()
    elementos += cap_remuneraciones()
    elementos += cap_activo_fijo()
    elementos += cap_f29()
    elementos += cap_f22()
    elementos += cap_cierres()
    elementos += cap_configuracion()
    elementos += cap_problemas()
    elementos += cap_glosario()
    elementos += cap_anexos()

    # multiBuild: la primera pasada numera, la segunda arma el índice.
    doc.multiBuild(elementos)
    return salida


def main() -> int:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "Manual-ContaFlow.pdf"
    ruta_final = construir(destino)
    tamano = ruta_final.stat().st_size / 1024
    print(f"Manual generado: {ruta_final}  ({tamano:,.0f} KB)")
    print(f"Cuentas documentadas: {len(GLOSARIO_CUENTAS)}")
    print(f"Secciones con marcador: {len(_anclas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
