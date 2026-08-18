# Manual de uso — ContAll

Guía práctica del ciclo contable mensual completo.

---

## 1. Puesta en marcha

### Crear la empresa

*Empresas → Nueva empresa*. Lo mínimo es RUT y razón social; el resto ayuda a que los
informes salgan completos.

El **régimen tributario** define la tasa de Primera Categoría que aplica el F22:

| Régimen | Tasa | Notas |
|---|---|---|
| 14 A — Semi Integrado | 27% | Empresas grandes |
| 14 D N°3 — Pro Pyme General | 25% | El más común en PyMEs |
| 14 D N°8 — Pro Pyme Transparente | Liberado | Tributan los dueños en su Global Complementario |
| Renta Presunta | 25% | Sobre renta presunta, no efectiva |

La **tasa de PPM** se usa para el código 62 del F29. Si no la conoces, revisa tu última
declaración: aparece en el código 115.

Al guardar se crea el plan de cuentas completo y las cuentas por defecto quedan
preconfiguradas. Ya puedes registrar documentos.

### Cargar indicadores

*Maestros → Indicadores*. Necesarios sólo para liquidaciones de sueldo:

- **UF** del último día del mes → topes imponibles y planes de Isapre.
- **UTM** del mes → tabla del Impuesto Único.
- **Ingreso mínimo** → tope de la gratificación Art. 50.

Sin estos tres valores, el sistema se niega a liquidar y te dice cuál falta.

### Revisar las cuentas por defecto

*Configuración → Cuentas contables*. Define qué cuenta usa cada asiento automático.
Vienen listas, pero si por ejemplo quieres que las compras vayan a «Mercaderías» en
vez de «Compras del giro», cámbialo aquí una vez y todos los asientos futuros lo respetan.

---

## 2. El mes a mes

Selecciona el **período de trabajo** (mes y año) en la barra superior. Todas las
pantallas trabajan sobre ese período.

### Registrar ventas

*Ventas → Registrar documento*.

- **Factura electrónica (33)**: elige *«Ingreso el NETO»* y escribe el neto. El IVA
  se calcula al 19% y el total se actualiza en vivo.
- **Boleta electrónica (39)**: elige *«Ingreso el TOTAL con IVA incluido»* y escribe lo
  que dice la boleta. El sistema despeja el neto y el IVA solos.
- **Factura exenta (34)** o **boleta exenta (41)**: el monto va en «Exento», sin IVA.
- **Nota de crédito (61)**: registra los montos **en positivo** e indica el documento
  referenciado en la sección *Referencia*. El sistema resta en los libros e invierte
  el asiento contable automáticamente.

El **período tributario** puede diferir de la fecha de emisión: es el mes en que el
documento se declara en el F29. Normalmente coinciden.

Al guardar con «Generar el asiento contable» marcado, se crea el asiento:

```
Clientes                      1.190.000
    Ventas afectas                        1.000.000
    IVA débito fiscal                       190.000
```

Si la venta fue al contado, despliega *Imputación contable* y elige «Caja» o «Banco»
como contrapartida.

### Registrar compras

*Compras → Registrar documento*. Igual que las ventas, más un campo clave:

**Tipo de compra** (lo exige el Registro de Compras del SII):

| Tipo | Qué hace |
|---|---|
| Del giro | IVA a crédito fiscal normal |
| Activo fijo | IVA a la cuenta de crédito fiscal de activo fijo (código 525) |
| Supermercado | Se informa aparte (códigos 553/554) |
| IVA uso común | Se le aplica el factor de proporcionalidad |
| IVA no recuperable | El IVA va a gasto, no a crédito |

### Boletas de honorarios

*Honorarios*. Al registrar una boleta **recibida**, el sistema calcula la retención con
la tasa del año (14,5% en 2025, 15,25% en 2026) y genera:

```
Honorarios profesionales        500.000
    Retención 2ª categoría                 72.500
    Honorarios por pagar                  427.500
```

La retención aparece en el código 151 del F29.

### Asientos manuales

*Contabilidad → Comprobantes → Nuevo asiento*, para todo lo que no es un documento
tributario: pagos, cobros, provisiones, ajustes, aportes de capital.

El formulario suma el debe y el haber en vivo y muestra la diferencia. **El botón de
guardar permanece deshabilitado mientras el asiento no cuadre.** Una línea no puede
tener monto en el debe y en el haber a la vez: al escribir en uno, el otro se limpia.

---

## 3. Remuneraciones

### Fichar trabajadores

*Remuneraciones → Trabajadores*. Datos que afectan el cálculo:

- **Tipo de contrato** → tasa del seguro de cesantía (indefinido: 0,6% trabajador +
  2,4% empleador; plazo fijo: 3% sólo empleador).
- **Gratificación Art. 50** → suma 25% de lo devengado con tope de 4,75 ingresos
  mínimos al año.
- **Isapre con plan en UF** → si el plan supera el 7% legal, la diferencia se descuenta
  como «salud adicional».
- **Jubilado** → no cotiza en AFP ni paga SIS.
- **Cargas familiares + tramo** → asignación familiar (no imponible, la paga el Estado).

### Liquidar

*Remuneraciones → Liquidaciones*.

- **Calcular todos con datos base**: usa el sueldo base y las asignaciones fijas de la
  ficha, 30 días trabajados. Ideal para el mes normal.
- **Calcular liquidación individual**: para quien tuvo horas extra, bonos, comisiones,
  anticipos o trabajó menos días.

Recalcular a alguien reemplaza su liquidación anterior del mismo mes.

Cada liquidación se descarga en PDF con línea de firma.

### Centralizar

*Remuneraciones → Libro de remuneraciones → Centralizar en contabilidad*. Genera un
asiento con los totales del mes: sueldos, gratificaciones, leyes sociales y mutual al
debe; cotizaciones, impuesto único y líquido por pagar al haber.

El **impuesto único** retenido alimenta el código 48 del F29.

---

## 4. Activo fijo

*Activo fijo*. Registra el bien con su vida útil según la tabla del SII (el campo
Categoría sugiere las vidas útiles oficiales):

| Bien | Vida útil normal |
|---|---|
| Equipos de computación | 6 años (72 meses) |
| Muebles y enseres | 7 años (84 meses) |
| Vehículos | 7 años (84 meses) |
| Maquinarias | 15 años (180 meses) |
| Instalaciones | 10 años (120 meses) |
| Construcciones de material sólido | 80 años |

Marca **depreciación acelerada** para dividir la vida útil por 3 (mínimo 12 meses).

*Ver tabla* muestra el calendario mes a mes hasta el final de la vida útil.
**Contabilizar depreciación del mes** genera el asiento de todos los activos vigentes.
La depreciación empieza el mes **siguiente** al de la adquisición.

Al **dar de baja** un activo, indica el valor de venta (0 si es desecho): el sistema
calcula la utilidad o pérdida contra el valor libro y arma el asiento.

---

## 5. Cierre del mes

Orden recomendado:

1. Registra **todas** las compras, ventas y honorarios del mes.
2. Liquida y **centraliza remuneraciones**.
3. **Contabiliza la depreciación** del activo fijo.
4. Registra pagos, cobros y ajustes.
5. Revisa el **Balance de 8 columnas**: las sumas deben cuadrar.
6. Genera la **propuesta de F29** y guárdala.
7. Declara en el sitio del SII usando la propuesta como referencia.
8. **Cierra el período** en *Contabilidad → Períodos* para que nadie lo altere.
9. Crea un **respaldo**.

### Leer la propuesta de F29

*Formulario 29*. Los códigos vienen agrupados como en el formulario oficial.

Lo esencial:

- **537 Total débitos** — el IVA que cobraste.
- **538 Total créditos** — el IVA que pagaste.
- **504 Remanente del mes anterior** — se toma solo del F29 guardado el mes pasado.
- **89 IVA a pagar** — cuando los débitos superan a los créditos.
- **77 Remanente para el mes siguiente** — cuando ocurre lo contrario.
- **563 Monto neto de ventas** — base de los PPM.
- **62 PPM neto determinado** — 563 × tu tasa de PPM.
- **91 Total a pagar** — IVA + PPM + retenciones.

Puedes sobrescribir el remanente anterior, la tasa de PPM o agregar crédito SENCE
en los campos de arriba y pulsar *Recalcular*.

**Guardar el F29** deja registrado el remanente del código 77, que el mes siguiente
aparecerá solo en el código 504. Es lo que encadena los períodos: guárdalo siempre.

---

## 6. Cierre del año

1. Cierra los 12 meses.
2. Revisa el **Estado de Resultados** y el **Estado de Situación Financiera** anuales.
3. Genera la propuesta de **F22** en *Formulario 22*, completando a mano:
   - **Agregados**: gastos rechazados, multas fiscales, gastos sin respaldo, Art. 21 LIR.
   - **Deducciones**: ingresos no renta y rentas exentas.
   - **Pérdida de arrastre** de ejercicios anteriores.
   - **PPM pagados** durante el año (actualizados).
4. Genera el **asiento de cierre de ejercicio** en *Contabilidad → Períodos*: traspasa
   todas las cuentas de resultado a «Resultado del ejercicio», dejando el estado de
   resultados en cero al 31 de diciembre.
5. Respalda.

> El F22 no incluye corrección monetaria ni la determinación de los registros
> empresariales (RAI, DDAN, REX, SAC). Esos análisis van aparte.

---

## 7. Respaldos

*Configuración → Respaldos*. Crea uno antes de cerrar un ejercicio, antes de restaurar
y al menos una vez al mes.

Restaurar reemplaza **todos** los datos de **todas** las empresas por los del respaldo,
pero antes guarda automáticamente una copia del estado actual (`antes-de-restaurar-…`).
Después de restaurar, cierra y vuelve a abrir ContAll.

Los respaldos están en `C:\Users\<tu usuario>\AppData\Local\ContAll\respaldos\`.
Cópialos a un disco externo o a la nube: si se pierde el disco, se pierde todo.

---

## Preguntas frecuentes

**¿Se conecta al SII?**
No. ContAll es completamente offline. Los documentos se ingresan a mano o desde tus
propios registros, y los formularios son propuestas para traspasar al sitio del SII.

**¿Puedo llevar varias empresas?**
Sí, sin límite. Cada una es independiente. Cambia entre ellas con el selector superior.

**Registré un documento con error.**
Anúlalo desde el libro correspondiente: se marca como anulado, sale de los libros de IVA
y su asiento contable se elimina. Después vuelve a registrarlo bien.

**No me deja registrar en un mes.**
Está cerrado. Reábrelo en *Contabilidad → Períodos*.

**El balance está descuadrado.**
Revisa el Balance de 8 columnas buscando cuentas con saldos raros, y el Libro Diario del
período. Como el sistema rechaza asientos descuadrados, casi siempre es una cuenta mal
imputada (un gasto cargado a una cuenta de activo, por ejemplo), no un descuadre real.

**Cambió el ingreso mínimo / las tasas de AFP.**
Ingreso mínimo y UF/UTM: *Maestros → Indicadores*. Tasas de AFP y mutual:
*Configuración → Parámetros*.

**¿Puedo usarlo en más de un computador?**
Sí, copiando `contaflow.db` entre equipos. Pero no lo uses en dos a la vez sobre el
mismo archivo compartido: no está diseñado para acceso concurrente en red.
