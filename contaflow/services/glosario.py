"""Diccionario de uso del plan de cuentas.

Para cada cuenta imputable describe qué registra, cuándo se carga (debe) y
cuándo se abona (haber). Alimenta el manual en PDF y sirve de referencia
para quien recién empieza a contabilizar.

Formato: código → (qué registra, se carga cuando…, se abona cuando…)
"""
from __future__ import annotations

GLOSARIO_CUENTAS: dict[str, tuple[str, str, str]] = {

    # ------------------------------------------------ 1.1.01 Efectivo
    "1.1.01.001": (
        "Dinero en efectivo que mantiene la empresa en sus dependencias.",
        "Se recibe dinero en efectivo: cobro a un cliente, aporte de un socio, giro del banco.",
        "Sale dinero en efectivo: pago a proveedor, depósito en el banco, gasto menor.",
    ),
    "1.1.01.002": (
        "Fondo fijo en efectivo para gastos menores del día a día.",
    "Se crea o repone el fondo fijo con dinero de caja o banco.",
        "Se rinden los gastos pagados con el fondo, traspasándolos a la cuenta de gasto correspondiente.",
    ),
    "1.1.01.003": (
        "Saldo de la cuenta corriente bancaria de la empresa. Es la cuenta que se "
        "concilia contra la cartola.",
        "Ingresa dinero: depósitos, transferencias recibidas, cobros de clientes.",
        "Sale dinero: cheques girados, transferencias enviadas, cargos y comisiones del banco.",
    ),
    "1.1.01.004": (
        "Saldo de la cuenta vista o chequera electrónica.",
        "Ingresan abonos y transferencias a la cuenta vista.",
        "Se pagan giros, transferencias o compras con esa cuenta.",
    ),
    "1.1.01.005": (
        "Depósitos a plazo tomados con excedentes de caja.",
        "Se toma el depósito, traspasando el dinero desde el banco.",
        "Vence el depósito y el capital vuelve al banco. Los intereses se abonan a 4.2.01.001.",
    ),
    "1.1.01.006": (
        "Cuotas de fondos mutuos u otros instrumentos de liquidez inmediata.",
        "Se invierte dinero en el fondo.",
        "Se rescatan cuotas. La ganancia del rescate se abona a 4.2.01.001.",
    ),

    # ------------------------------------------------ 1.1.02 Deudores
    "1.1.02.001": (
        "Lo que los clientes deben por facturas de venta a crédito. Es la cuenta "
        "que usa el sistema al contabilizar una venta si no indicas otra contrapartida.",
        "Se emite una factura de venta a crédito (por el total, con IVA incluido).",
        "El cliente paga, o se le emite una nota de crédito.",
    ),
    "1.1.02.002": (
        "Cheques a fecha, letras y pagarés recibidos de clientes para documentar su deuda.",
        "El cliente entrega un documento en respaldo de su deuda.",
        "El documento se cobra, se deposita o se protesta.",
    ),
    "1.1.02.003": (
        "Cheques recibidos que aún no se depositan en el banco.",
        "Se recibe el cheque del cliente.",
        "El cheque se deposita (pasa a la cuenta de banco) o se devuelve.",
    ),
    "1.1.02.004": (
        "Deudas a favor de la empresa que no provienen de ventas del giro: "
        "reembolsos, indemnizaciones de seguros, cobros a terceros.",
        "Nace el derecho a cobrar a un tercero.",
        "El tercero paga.",
    ),
    "1.1.02.005": (
        "Provisión por clientes que probablemente no pagarán. Es una cuenta de "
        "activo con saldo acreedor: rebaja el total de clientes en el balance.",
        "Se recupera una deuda que estaba provisionada, o se castiga definitivamente.",
        "Se constituye o aumenta la provisión, con cargo a 5.2.03.003.",
    ),

    # ------------------------------------------------ 1.1.03 Relacionadas
    "1.1.03.001": (
        "Movimientos entre la empresa y sus socios que no son remuneración ni "
        "retiro formal. Ojo: un saldo deudor alto puede ser cuestionado por el SII.",
        "El socio retira dinero o la empresa paga un gasto personal suyo.",
        "El socio devuelve el dinero o se regulariza como retiro.",
    ),
    "1.1.03.002": (
        "Dinero entregado a proveedores antes de recibir el bien o servicio.",
        "Se paga el anticipo al proveedor.",
        "Llega la factura definitiva y el anticipo se descuenta de la deuda.",
    ),
    "1.1.03.003": (
        "Préstamos y anticipos de sueldo entregados a trabajadores.",
        "Se entrega el anticipo o préstamo al trabajador.",
        "Se descuenta de su liquidación de sueldo o lo devuelve.",
    ),

    # ------------------------------------------------ 1.1.04 Impuestos por recuperar
    "1.1.04.001": (
        "IVA soportado en las compras del giro, que se descuenta del IVA de las "
        "ventas. El sistema la usa automáticamente al registrar una compra.",
        "Se recibe una factura de compra afecta a IVA (por el monto del IVA).",
        "Se cierra el período: el crédito se compensa contra el débito fiscal al declarar el F29.",
    ),
    "1.1.04.002": (
        "IVA de las compras de activo fijo. Se separa porque en el F29 va en los "
        "códigos 524 y 525, distintos de las compras del giro.",
        "Se compra un bien del activo fijo con IVA, y clasificas la compra como «Activo fijo».",
        "Se compensa contra el débito fiscal al declarar el período.",
    ),
    "1.1.04.003": (
        "Crédito fiscal que sobró de meses anteriores porque las compras superaron "
        "a las ventas. Corresponde al código 77 del F29, que pasa al 504 del mes siguiente.",
        "El F29 del mes cierra con más crédito que débito.",
        "Se usa el remanente para pagar el IVA de un mes posterior.",
    ),
    "1.1.04.004": (
        "Pagos provisionales mensuales enterados al SII, que son un anticipo del "
        "impuesto a la renta anual.",
        "Se paga el PPM del mes junto con el F29.",
        "Se imputan los PPM al impuesto a la renta en la declaración anual (F22).",
    ),
    "1.1.04.005": (
        "Franquicia por gastos de capacitación con cargo al SENCE, recuperable "
        "vía F29 (código 66).",
        "Se ejecuta una capacitación con derecho a la franquicia.",
        "Se descuenta el crédito en el F29 o se recibe la devolución.",
    ),
    "1.1.04.006": (
        "Impuesto a la renta pagado en exceso, que el SII devolverá.",
        "La declaración anual arroja saldo a favor.",
        "El SII deposita la devolución.",
    ),
    "1.1.04.007": (
        "Retenciones que terceros practicaron sobre boletas de honorarios emitidas "
        "por la empresa o su dueño (contribuyentes de segunda categoría).",
        "Se emite una boleta de honorarios y el pagador retiene el impuesto.",
        "La retención se imputa al impuesto anual o se recibe su devolución.",
    ),

    # ------------------------------------------------ 1.1.05 Existencias
    "1.1.05.001": (
        "Bienes comprados para revender, valorizados al costo de adquisición.",
        "Se compran mercaderías (si llevas inventario permanente).",
        "Se venden, con cargo al costo de ventas (5.1.01.001), o se dan de baja por merma.",
    ),
    "1.1.05.002": (
        "Insumos que se transforman en el proceso productivo.",
        "Se compran materias primas.",
        "Pasan a producción, con cargo a productos en proceso o a costo directo.",
    ),
    "1.1.05.003": (
        "Producción a medio terminar al cierre del período.",
        "Se incorporan materiales, mano de obra y gastos de fabricación.",
        "La producción se termina y pasa a productos terminados.",
    ),
    "1.1.05.004": (
        "Producción terminada, aún no vendida.",
        "Termina la fabricación de un lote.",
        "Se vende el producto, con cargo al costo de ventas.",
    ),
    "1.1.05.005": (
        "Insumos de consumo interno: repuestos, envases y material de embalaje.",
        "Se compran los suministros.",
        "Se consumen, con cargo a la cuenta de gasto que corresponda.",
    ),

    # ------------------------------------------------ 1.1.06 Anticipados
    "1.1.06.001": (
        "Primas de seguro pagadas por adelantado que cubren meses futuros.",
        "Se paga la póliza completa.",
        "Cada mes se lleva a gasto la parte devengada (cargo a 5.2.02.010).",
    ),
    "1.1.06.002": (
        "Arriendos pagados por adelantado (garantías de renta, meses anticipados).",
        "Se paga el arriendo anticipado.",
        "Se devenga cada mes, con cargo a 5.2.02.001.",
    ),
    "1.1.06.003": (
        "Cualquier otro desembolso que beneficia a períodos futuros: licencias "
        "anuales, publicidad contratada por adelantado.",
        "Se paga el servicio anticipado.",
        "Se devenga la porción del período, con cargo a la cuenta de gasto correspondiente.",
    ),

    # ------------------------------------------------ 1.2.01 Activo fijo
    "1.2.01.001": (
        "Terrenos de propiedad de la empresa. No se deprecian nunca.",
        "Se compra el terreno (incluye gastos notariales y de inscripción).",
        "Se vende o se aporta el terreno.",
    ),
    "1.2.01.002": (
        "Edificios, galpones y obras de infraestructura. Vida útil SII: 80 años "
        "en material sólido, 20 en estructura metálica.",
        "Se construye o adquiere el inmueble, y por las mejoras que alargan su vida útil.",
        "Se vende o se da de baja la construcción.",
    ),
    "1.2.01.003": (
        "Maquinaria y equipos productivos. Vida útil SII: 15 años.",
        "Se compra la maquinaria, incluyendo flete e instalación hasta dejarla operativa.",
        "Se vende o da de baja la máquina.",
    ),
    "1.2.01.004": (
        "Escritorios, sillas, estanterías y mobiliario en general. Vida útil SII: 7 años.",
        "Se compran muebles y enseres.",
        "Se venden o dan de baja.",
    ),
    "1.2.01.005": (
        "Computadores, notebooks, servidores e impresoras. Vida útil SII: 6 años.",
        "Se compran equipos computacionales.",
        "Se venden, dan de baja o quedan obsoletos.",
    ),
    "1.2.01.006": (
        "Automóviles, camionetas y camiones. Vida útil SII: 7 años. Atención: el "
        "IVA de los automóviles suele ser no recuperable (revisa la restricción del giro).",
        "Se compra el vehículo, incluyendo inscripción y accesorios permanentes.",
        "Se vende o da de baja el vehículo.",
    ),
    "1.2.01.007": (
        "Instalaciones eléctricas, sanitarias, de redes y habilitación de locales. "
        "Vida útil SII: 10 años.",
        "Se ejecuta la instalación o habilitación.",
        "Se retira o da de baja la instalación.",
    ),
    "1.2.01.008": (
        "Herramientas de trabajo con vida útil mayor a un año. Vida útil SII: "
        "3 años las livianas, 8 las pesadas.",
        "Se compran las herramientas.",
        "Se dan de baja por desgaste o pérdida.",
    ),

    # ------------------------------------------------ 1.2.02 Depreciación acumulada
    "1.2.02.002": (
        "Desgaste acumulado de las construcciones. Cuenta de activo con saldo "
        "acreedor: rebaja el valor del bien en el balance.",
        "Se da de baja o vende el inmueble (se elimina la depreciación acumulada).",
        "Cada mes, al contabilizar la depreciación del período.",
    ),
    "1.2.02.003": (
        "Desgaste acumulado de maquinarias y equipos.",
        "Se da de baja o vende la maquinaria.",
        "Cada mes, con la depreciación del período.",
    ),
    "1.2.02.004": (
        "Desgaste acumulado de muebles y útiles. Es la cuenta que el sistema usa "
        "por defecto si el activo no tiene una propia.",
        "Se dan de baja o venden los muebles.",
        "Cada mes, con la depreciación del período.",
    ),
    "1.2.02.005": (
        "Desgaste acumulado de los equipos computacionales.",
        "Se dan de baja o venden los equipos.",
        "Cada mes, con la depreciación del período.",
    ),
    "1.2.02.006": (
        "Desgaste acumulado de los vehículos.",
        "Se vende o da de baja el vehículo.",
        "Cada mes, con la depreciación del período.",
    ),
    "1.2.02.007": (
        "Desgaste acumulado de las instalaciones.",
        "Se retiran o dan de baja las instalaciones.",
        "Cada mes, con la depreciación del período.",
    ),

    # ------------------------------------------------ 1.2.03 Intangibles
    "1.2.03.001": (
        "Licencias de software y desarrollos informáticos de uso prolongado.",
        "Se adquiere la licencia o se capitaliza el desarrollo.",
        "Se da de baja el software.",
    ),
    "1.2.03.002": (
        "Marcas, patentes y derechos inscritos a nombre de la empresa.",
        "Se inscribe o compra el derecho.",
        "Se vende o caduca el derecho.",
    ),
    "1.2.03.003": (
        "Amortización acumulada de los intangibles. Rebaja su valor en el balance.",
        "Se da de baja el intangible.",
        "Cada período, con cargo a 5.2.03.002.",
    ),

    # ------------------------------------------------ 1.2.04 Inversiones
    "1.2.04.001": (
        "Participación en otras sociedades (acciones o derechos sociales).",
        "Se adquiere o aumenta la participación.",
        "Se vende o disminuye la participación.",
    ),
    "1.2.04.002": (
        "Diferencias temporarias que generarán menor impuesto en el futuro "
        "(por ejemplo, pérdidas tributarias de arrastre).",
        "Nace o aumenta el activo por impuesto diferido.",
        "Se realiza la diferencia y el beneficio se consume.",
    ),
    "1.2.04.003": (
        "Garantías entregadas y recuperables: arriendos, servicios básicos, "
        "boletas de garantía.",
        "Se entrega el depósito en garantía.",
        "Se devuelve la garantía o se aplica al pago.",
    ),

    # ------------------------------------------------ 2.1.01 Financieras CP
    "2.1.01.001": (
        "Créditos bancarios cuyo vencimiento cae dentro de los próximos 12 meses.",
        "Se pagan las cuotas de capital.",
        "Se recibe el préstamo, o se reclasifica desde largo plazo lo que vence en el año.",
    ),
    "2.1.01.002": (
        "Saldo utilizado de la línea de crédito asociada a la cuenta corriente.",
        "Se paga o repone la línea.",
        "Se gira contra la línea de crédito.",
    ),
    "2.1.01.003": (
        "Cuotas de leasing con vencimiento en los próximos 12 meses.",
        "Se pagan las cuotas del leasing.",
        "Se contrata el leasing, o se reclasifica desde largo plazo.",
    ),
    "2.1.01.004": (
        "Intereses ya devengados pero todavía no pagados.",
        "Se pagan los intereses.",
        "Se devengan los intereses del período, con cargo a 5.3.01.001.",
    ),

    # ------------------------------------------------ 2.1.02 Acreedores
    "2.1.02.001": (
        "Lo que la empresa debe a proveedores por facturas de compra a crédito. "
        "Es la contrapartida que el sistema usa al contabilizar una compra.",
        "Se paga al proveedor, o él emite una nota de crédito.",
        "Se recibe una factura de compra a crédito (por el total, con IVA incluido).",
    ),
    "2.1.02.002": (
        "Cheques, letras y pagarés que la empresa entregó para documentar sus deudas.",
        "Se paga el documento a su vencimiento.",
        "Se emite el documento en respaldo de una deuda.",
    ),
    "2.1.02.003": (
        "Deudas que no provienen de compras del giro: servicios profesionales, "
        "reembolsos pendientes, cuentas por pagar varias.",
        "Se paga la obligación.",
        "Nace la obligación con el tercero.",
    ),
    "2.1.02.004": (
        "Dinero recibido de clientes antes de entregar el bien o servicio. Es un "
        "pasivo hasta que se emite la factura.",
        "Se emite la factura definitiva y el anticipo se aplica a la deuda del cliente.",
        "El cliente paga por adelantado.",
    ),
    "2.1.02.005": (
        "Líquido pendiente de pago a profesionales que emitieron boleta de "
        "honorarios. El sistema la usa al contabilizar una boleta recibida.",
        "Se paga el líquido al profesional.",
        "Se registra la boleta de honorarios recibida (por el bruto menos la retención).",
    ),

    # ------------------------------------------------ 2.1.03 Impuestos por pagar
    "2.1.03.001": (
        "IVA recargado en las ventas, que la empresa recauda para el Fisco. "
        "El sistema la usa automáticamente al contabilizar una venta.",
        "Se cierra el período y se compensa contra el crédito fiscal al declarar el F29.",
        "Se emite una factura o boleta afecta a IVA (por el monto del IVA).",
    ),
    "2.1.03.002": (
        "IVA neto a enterar al Fisco una vez compensados débitos y créditos "
        "(código 89 del F29).",
        "Se paga el IVA al SII.",
        "Se determina el IVA del período al cerrar el F29.",
    ),
    "2.1.03.003": (
        "PPM del mes, determinado y pendiente de pago (código 62 del F29).",
        "Se paga el PPM junto con el F29.",
        "Se determina el PPM del período.",
    ),
    "2.1.03.004": (
        "Retención practicada sobre boletas de honorarios recibidas, que la "
        "empresa debe enterar al SII (código 151 del F29).",
        "Se entera la retención al SII con el F29 del mes siguiente.",
        "Se registra una boleta de honorarios recibida.",
    ),
    "2.1.03.005": (
        "Impuesto Único de Segunda Categoría retenido a los trabajadores "
        "(código 48 del F29).",
        "Se entera el impuesto al SII.",
        "Se centralizan las remuneraciones del mes.",
    ),
    "2.1.03.006": (
        "Impuesto de Primera Categoría determinado en la declaración anual y "
        "pendiente de pago.",
        "Se paga el impuesto en abril.",
        "Se determina el impuesto al cerrar el ejercicio.",
    ),
    "2.1.03.007": (
        "Impuestos específicos recargados en las ventas: bebidas alcohólicas y "
        "analcohólicas (ILA), combustibles, artículos suntuarios.",
        "Se enteran los impuestos adicionales al SII.",
        "Se emite un documento con impuesto adicional.",
    ),
    "2.1.03.008": (
        "IVA retenido al proveedor en operaciones con cambio de sujeto "
        "(facturas de compra), que la empresa entera en su lugar.",
        "Se entera la retención al SII.",
        "Se emite una factura de compra con retención.",
    ),

    # ------------------------------------------------ 2.1.04 Previsionales
    "2.1.04.001": (
        "Líquido que se debe a los trabajadores por sus remuneraciones del mes.",
        "Se pagan los sueldos.",
        "Se centralizan las remuneraciones del mes.",
    ),
    "2.1.04.002": (
        "Cotizaciones previsionales retenidas y aportes del empleador, "
        "pendientes de pago en Previred.",
        "Se pagan las cotizaciones (hasta el día 10 o 13 del mes siguiente).",
        "Se centralizan las remuneraciones del mes.",
    ),
    "2.1.04.003": (
        "Cotización de salud (7% legal más el adicional de Isapre) pendiente de pago.",
        "Se paga la cotización de salud.",
        "Se centralizan las remuneraciones del mes.",
    ),
    "2.1.04.004": (
        "Aportes al seguro de cesantía, del trabajador y del empleador, pendientes de pago.",
        "Se paga el seguro de cesantía en Previred.",
        "Se centralizan las remuneraciones del mes.",
    ),
    "2.1.04.005": (
        "Cotización a la mutualidad de seguridad (Ley 16.744), de cargo exclusivo del empleador.",
        "Se paga la cotización a la mutual.",
        "Se centralizan las remuneraciones del mes.",
    ),
    "2.1.04.006": (
        "Aportes y descuentos de la caja de compensación (créditos sociales, "
        "asignación familiar por recuperar).",
        "Se paga a la caja o se recupera la asignación familiar.",
        "Se generan descuentos o aportes del mes.",
    ),
    "2.1.04.007": (
        "Provisión del feriado legal que los trabajadores han devengado y aún no toman.",
        "El trabajador toma vacaciones o se le pagan en el finiquito.",
        "Se provisiona el feriado devengado del período.",
    ),
    "2.1.04.008": (
        "Provisión de la indemnización por años de servicio a todo evento, cuando "
        "está pactada.",
        "Se paga la indemnización al término del contrato.",
        "Se provisiona el período devengado.",
    ),

    # ------------------------------------------------ 2.1.05 Otros pasivos
    "2.1.05.001": (
        "Gastos ya devengados cuya factura aún no llega, para que el resultado "
        "del mes quede completo.",
        "Llega la factura definitiva y se reversa la provisión.",
        "Se provisiona el gasto al cierre del mes.",
    ),
    "2.1.05.002": (
        "Descuentos por resolución judicial (pensiones de alimentos, embargos) "
        "retenidos al trabajador.",
        "Se entera la retención al tribunal o al beneficiario.",
        "Se descuenta en la liquidación de sueldo.",
    ),
    "2.1.05.003": (
        "Ingresos cobrados por adelantado que corresponden a períodos futuros "
        "(suscripciones, contratos anuales).",
        "Se devenga el ingreso del período, abonando la cuenta de ventas.",
        "Se cobra por adelantado.",
    ),

    # ------------------------------------------------ 2.2.01 Largo plazo
    "2.2.01.001": (
        "Créditos bancarios cuyo vencimiento supera los 12 meses.",
        "Se reclasifica a corto plazo lo que vencerá dentro del año, o se prepaga.",
        "Se recibe el crédito de largo plazo.",
    ),
    "2.2.01.002": (
        "Cuotas de leasing con vencimiento posterior a 12 meses.",
        "Se reclasifica a corto plazo lo que vence en el año.",
        "Se contrata el leasing.",
    ),
    "2.2.01.003": (
        "Diferencias temporarias que generarán mayor impuesto en el futuro "
        "(por ejemplo, depreciación acelerada tributaria).",
        "Se revierte la diferencia temporaria.",
        "Nace o aumenta el pasivo por impuesto diferido.",
    ),

    # ------------------------------------------------ 3 Patrimonio
    "3.1.01.001": (
        "Capital efectivamente enterado por los socios o accionistas.",
        "Se disminuye formalmente el capital.",
        "Los socios aportan capital.",
    ),
    "3.1.01.002": (
        "Capital suscrito que los socios aún no pagan. Cuenta de patrimonio con "
        "saldo deudor: rebaja el capital en el balance.",
        "Se suscribe capital que queda pendiente de pago.",
        "El socio entera el aporte comprometido.",
    ),
    "3.1.01.003": (
        "Ajuste del capital propio por inflación (corrección monetaria).",
        "La corrección monetaria del ejercicio resulta negativa.",
        "Se aplica la revalorización del capital propio al cierre del ejercicio.",
    ),
    "3.1.02.001": (
        "Reserva que la ley o los estatutos obligan a mantener sin distribuir.",
        "Se aplica la reserva a absorber pérdidas.",
        "Se destina utilidad a la reserva.",
    ),
    "3.1.02.002": (
        "Reservas voluntarias acordadas por los socios.",
        "Se libera o aplica la reserva.",
        "Se acuerda constituirla con cargo a utilidades.",
    ),
    "3.1.03.001": (
        "Utilidades de ejercicios anteriores que no se han retirado ni distribuido.",
        "Se distribuyen o se absorben pérdidas.",
        "Se traspasa la utilidad del ejercicio recién cerrado.",
    ),
    "3.1.03.002": (
        "Pérdidas de ejercicios anteriores pendientes de absorber. Cuenta de "
        "patrimonio con saldo deudor.",
        "Se traspasa la pérdida del ejercicio cerrado.",
        "Se absorbe la pérdida con utilidades o aportes posteriores.",
    ),
    "3.1.03.003": (
        "Resultado del ejercicio en curso. El asiento de cierre traspasa aquí el "
        "saldo de todas las cuentas de resultado.",
        "El ejercicio cierra con pérdida, o se traspasa el saldo a utilidades acumuladas.",
        "El ejercicio cierra con utilidad.",
    ),
    "3.1.03.004": (
        "Retiros de los socios o dividendos provisorios del ejercicio. Cuenta de "
        "patrimonio con saldo deudor: rebaja el patrimonio.",
        "El socio retira dinero o bienes de la empresa.",
        "Se regulariza el retiro contra utilidades al cierre.",
    ),

    # ------------------------------------------------ 4 Ingresos
    "4.1.01.001": (
        "Ventas del giro gravadas con IVA, registradas por su monto neto. Es la "
        "cuenta de ingreso que el sistema usa por defecto.",
        "Se emite una nota de crédito que anula o rebaja una venta.",
        "Se emite una factura o boleta afecta (por el neto, sin IVA).",
    ),
    "4.1.01.002": (
        "Ventas no gravadas con IVA: servicios exentos, operaciones fuera del "
        "hecho gravado.",
        "Se emite una nota de crédito sobre una venta exenta.",
        "Se emite una factura o boleta exenta.",
    ),
    "4.1.01.003": (
        "Ventas al exterior. Son exentas de IVA y dan derecho a recuperar el "
        "crédito fiscal asociado (código 585 del F29).",
        "Se emite una nota de crédito de exportación.",
        "Se emite una factura de exportación.",
    ),
    "4.1.01.004": (
        "Ingresos por prestación de servicios, separados de la venta de bienes "
        "cuando conviene distinguirlos.",
        "Se anula o rebaja el servicio facturado.",
        "Se factura el servicio prestado.",
    ),
    "4.1.01.005": (
        "Descuentos comerciales y devoluciones de clientes. Cuenta de ingreso con "
        "saldo deudor: rebaja las ventas brutas.",
        "Se concede un descuento o el cliente devuelve mercadería.",
        "Se reversa un descuento otorgado por error.",
    ),
    "4.2.01.001": (
        "Intereses ganados por depósitos, fondos mutuos o financiamiento a clientes.",
        "Se reversa un interés registrado de más.",
        "Se devengan o cobran los intereses.",
    ),
    "4.2.01.002": (
        "Ganancia cuando un activo fijo se vende por sobre su valor libro. El "
        "sistema la calcula sola al dar de baja un activo.",
        "Se corrige una utilidad registrada de más.",
        "Se vende un activo fijo por sobre su valor libro.",
    ),
    "4.2.01.003": (
        "Ingresos por arrendar bienes de la empresa a terceros.",
        "Se anula o rebaja el arriendo facturado.",
        "Se devenga o cobra el arriendo.",
    ),
    "4.2.01.004": (
        "Ganancia por variación del tipo de cambio en activos y pasivos en "
        "moneda extranjera.",
        "Se revierte la diferencia al liquidar la operación.",
        "El tipo de cambio evoluciona a favor de la empresa.",
    ),
    "4.2.01.005": (
        "Efecto positivo de la corrección monetaria del ejercicio.",
        "Se reversa el ajuste.",
        "La corrección monetaria arroja un abono a resultado.",
    ),
    "4.2.01.006": (
        "Ingresos que no encajan en ninguna categoría anterior: indemnizaciones, "
        "premios, recuperaciones de gastos.",
        "Se anula el ingreso registrado.",
        "Se percibe o devenga el ingreso.",
    ),

    # ------------------------------------------------ 5.1 Costos
    "5.1.01.001": (
        "Costo de la mercadería efectivamente vendida, cuando se lleva inventario "
        "permanente.",
        "Se vende mercadería (por su costo, no por el precio de venta).",
        "Se devuelve mercadería vendida y vuelve al inventario.",
    ),
    "5.1.01.002": (
        "Costos directamente atribuibles a los servicios prestados.",
        "Se devengan los costos del servicio entregado.",
        "Se reversa un costo mal imputado.",
    ),
    "5.1.01.003": (
        "Remuneraciones del personal que participa directamente en la producción "
        "o en la prestación del servicio.",
        "Se centralizan las remuneraciones del personal directo.",
        "Se reclasifica el costo.",
    ),
    "5.1.01.004": (
        "Materiales consumidos directamente en la producción o el servicio.",
        "Se consumen los materiales en producción.",
        "Se devuelven materiales al inventario.",
    ),
    "5.1.01.005": (
        "Compras de bienes del giro cuando NO se lleva inventario permanente: el "
        "costo se reconoce al comprar. Es la cuenta que el sistema usa por defecto "
        "al contabilizar una compra.",
        "Se recibe una factura de compra del giro (por el neto, sin IVA).",
        "El proveedor emite una nota de crédito.",
    ),

    # ------------------------------------------------ 5.2.01 Personal
    "5.2.01.001": (
        "Sueldos base del personal administrativo y de ventas.",
        "Se centralizan las remuneraciones del mes.",
        "Se corrige un cargo excesivo.",
    ),
    "5.2.01.002": (
        "Gratificación legal (Art. 50: 25% de lo devengado con tope de 4,75 "
        "ingresos mínimos anuales) o la pactada en el contrato.",
        "Se centralizan las remuneraciones del mes.",
        "Se ajusta la gratificación provisionada.",
    ),
    "5.2.01.003": (
        "Recargo por horas trabajadas sobre la jornada ordinaria (mínimo 50%).",
        "Se centralizan las remuneraciones del mes.",
        "Se corrige el cálculo.",
    ),
    "5.2.01.004": (
        "Bonos de producción, metas, aguinaldos de fiestas patrias y navidad.",
        "Se pagan o devengan los bonos.",
        "Se reversa una provisión no utilizada.",
    ),
    "5.2.01.005": (
        "Aportes previsionales de cargo del empleador: SIS (1,88%) y seguro de "
        "cesantía (2,4% en contratos indefinidos).",
        "Se centralizan las remuneraciones del mes.",
        "Se ajusta el aporte calculado.",
    ),
    "5.2.01.006": (
        "Cotización a la mutualidad por accidentes del trabajo: 0,90% básico más "
        "la tasa adicional según el riesgo de la actividad.",
        "Se centralizan las remuneraciones del mes.",
        "Se ajusta la tasa aplicada.",
    ),
    "5.2.01.007": (
        "Indemnizaciones por años de servicio y sustitutiva del aviso previo "
        "pagadas al término de un contrato.",
        "Se paga el finiquito.",
        "Se aplica una provisión constituida previamente.",
    ),
    "5.2.01.008": (
        "Honorarios de profesionales independientes, por el monto bruto de la "
        "boleta. Es la cuenta que el sistema usa al registrar una boleta recibida.",
        "Se registra una boleta de honorarios recibida (por el bruto).",
        "Se anula la boleta.",
    ),
    "5.2.01.009": (
        "Asignaciones de colación y movilización. Son haberes no imponibles ni "
        "tributables mientras sean de monto razonable.",
        "Se centralizan las remuneraciones del mes.",
        "Se corrige el monto asignado.",
    ),
    "5.2.01.010": (
        "Cursos y capacitación del personal. Puede dar derecho a la franquicia SENCE.",
        "Se paga o devenga la capacitación.",
        "Se recupera parte vía crédito SENCE.",
    ),

    # ------------------------------------------------ 5.2.02 Generales
    "5.2.02.001": (
        "Arriendo de oficinas, locales, bodegas y equipos.",
        "Se devenga el arriendo del mes.",
        "Se reversa un cargo excesivo.",
    ),
    "5.2.02.002": (
        "Cuentas de electricidad, agua potable y gas.",
        "Llega la boleta o factura del servicio.",
        "Se recibe una nota de crédito de la empresa proveedora.",
    ),
    "5.2.02.003": (
        "Telefonía fija y móvil, internet y enlaces de datos.",
        "Llega la factura del servicio.",
        "Se recibe una nota de crédito.",
    ),
    "5.2.02.004": (
        "Papelería, útiles de escritorio, tóner y artículos de oficina.",
        "Se compran los materiales.",
        "Se devuelven al proveedor.",
    ),
    "5.2.02.005": (
        "Servicios de aseo, jardinería, seguridad y vigilancia.",
        "Se devenga el servicio del mes.",
        "Se recibe una nota de crédito.",
    ),
    "5.2.02.006": (
        "Reparaciones y mantenciones que conservan el bien sin aumentar su vida útil. "
        "Si la mejora alarga la vida útil, va al activo fijo en vez de a gasto.",
        "Se realiza la mantención o reparación.",
        "Se reclasifica el desembolso a activo fijo.",
    ),
    "5.2.02.007": (
        "Bencina, petróleo, lubricantes y peajes de los vehículos de la empresa.",
        "Se cargan combustibles.",
        "Se recibe una nota de crédito.",
    ),
    "5.2.02.008": (
        "Fletes de despacho, encomiendas y transporte de mercadería.",
        "Se contrata el flete.",
        "Se recibe una nota de crédito.",
    ),
    "5.2.02.009": (
        "Avisos, publicidad digital, material promocional y marketing.",
        "Se devenga la campaña o el aviso.",
        "Se recibe una nota de crédito.",
    ),
    "5.2.02.010": (
        "Primas de seguros de la empresa: incendio, responsabilidad civil, vehículos.",
        "Se devenga la prima del período.",
        "Se recibe la devolución de una prima no consumida.",
    ),
    "5.2.02.011": (
        "Patente municipal, permisos de circulación y derechos municipales.",
        "Se paga o devenga la patente.",
        "Se obtiene una devolución.",
    ),
    "5.2.02.012": (
        "Escrituras, notaría, conservador de bienes raíces y asesoría legal.",
        "Se paga el servicio notarial o legal.",
        "Se reclasifica el desembolso.",
    ),
    "5.2.02.013": (
        "Suscripciones a software, servicios en la nube, hosting y dominios.",
        "Se devenga el servicio del período.",
        "Se recibe una nota de crédito.",
    ),
    "5.2.02.014": (
        "Pasajes, alojamiento y viáticos de viajes de trabajo.",
        "Se incurre en el gasto de viaje.",
        "Se rinde un anticipo por un monto menor al entregado.",
    ),
    "5.2.02.015": (
        "Mantención de cuentas, comisiones bancarias e impuesto de timbres.",
        "El banco carga la comisión en la cartola.",
        "El banco reversa un cobro.",
    ),
    "5.2.02.016": (
        "Cuotas de asociaciones gremiales, colegios profesionales y membresías.",
        "Se devenga la cuota del período.",
        "Se reversa una cuota no utilizada.",
    ),
    "5.2.02.017": (
        "Gastos operacionales menores sin cuenta específica. Es la cuenta que el "
        "sistema propone por defecto para gastos generales; conviene mantenerla baja.",
        "Se incurre en un gasto sin cuenta propia.",
        "Se reclasifica a la cuenta que corresponde.",
    ),

    # ------------------------------------------------ 5.2.03 Depreciaciones
    "5.2.03.001": (
        "Depreciación del período de todo el activo fijo. El sistema la calcula y "
        "contabiliza automáticamente cada mes.",
        "Se procesa la depreciación mensual del activo fijo.",
        "Se corrige la depreciación registrada.",
    ),
    "5.2.03.002": (
        "Amortización del período de los activos intangibles.",
        "Se devenga la amortización del período.",
        "Se corrige el cálculo.",
    ),
    "5.2.03.003": (
        "Deudas de clientes reconocidas como incobrables.",
        "Se provisiona o castiga la deuda incobrable.",
        "Se recupera una deuda que estaba castigada.",
    ),

    # ------------------------------------------------ 5.3 No operacionales
    "5.3.01.001": (
        "Intereses de créditos, líneas y leasing, más comisiones de financiamiento.",
        "Se devengan o pagan los intereses.",
        "El banco reversa un cobro.",
    ),
    "5.3.01.002": (
        "Pérdida cuando un activo fijo se vende bajo su valor libro o se da de "
        "baja sin recuperar nada. El sistema la calcula sola en la baja.",
        "Se da de baja o vende el activo bajo su valor libro.",
        "Se corrige la pérdida registrada.",
    ),
    "5.3.01.003": (
        "Pérdida por variación del tipo de cambio en activos y pasivos en moneda "
        "extranjera.",
        "El tipo de cambio evoluciona en contra de la empresa.",
        "Se revierte la diferencia al liquidar la operación.",
    ),
    "5.3.01.004": (
        "Efecto negativo de la corrección monetaria del ejercicio.",
        "La corrección monetaria arroja un cargo a resultado.",
        "Se reversa el ajuste.",
    ),
    "5.3.01.005": (
        "Multas, intereses y reajustes por declaraciones fuera de plazo. "
        "Tributariamente es un gasto rechazado: se agrega a la RLI en el F22.",
        "Se paga una multa o interés fiscal.",
        "Se condona la multa.",
    ),
    "5.3.01.006": (
        "Desembolsos que la Ley de la Renta no acepta como gasto: gastos "
        "personales de los socios, desembolsos sin respaldo. Se agregan a la RLI.",
        "Se incurre en el gasto rechazado.",
        "Se reclasifica el desembolso.",
    ),
    "5.3.01.007": (
        "IVA soportado que no da derecho a crédito fiscal (automóviles, gastos sin "
        "relación con el giro) y que por tanto es un costo más.",
        "Se registra una compra clasificada como «IVA no recuperable».",
        "Se corrige la clasificación de la compra.",
    ),
    "5.4.01.001": (
        "Impuesto de Primera Categoría del ejercicio: 25% en el régimen Pro Pyme "
        "General, 27% en el Semi Integrado.",
        "Se determina el impuesto al cerrar el ejercicio.",
        "Se ajusta la provisión al presentar el F22.",
    ),

    # ------------------------------------------------ 9 Cuentas de orden
    "9.1.01.001": (
        "Registro informativo de documentos entregados en garantía. No afecta el "
        "resultado ni el patrimonio.",
        "Se entrega el documento en garantía.",
        "Se recupera el documento.",
    ),
    "9.1.01.002": (
        "Contrapartida de la cuenta anterior, para que el registro de orden cuadre.",
        "Se recupera el documento en garantía.",
        "Se entrega el documento en garantía.",
    ),
}


def cuentas_sin_glosario() -> list[str]:
    """Cuentas imputables del plan que aún no tienen descripción de uso."""
    from contaflow.services.plan_cuentas import PLAN_CUENTAS

    return [
        codigo for codigo, _n, _t, imputable, _f in PLAN_CUENTAS
        if imputable and codigo not in GLOSARIO_CUENTAS
    ]
