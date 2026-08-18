"""Pruebas del núcleo contable, tributario y previsional de ContAll.

Se ejecutan contra una base SQLite temporal (variable CONTAFLOW_DB_URL).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

os.environ.setdefault("CONTAFLOW_DATA", tempfile.mkdtemp(prefix="contaflow-test-"))
os.environ["CONTAFLOW_DB_URL"] = "sqlite:///" + str(
    Path(os.environ["CONTAFLOW_DATA"]) / "pruebas.db"
)

from contaflow.database import SessionLocal, crear_esquema  # noqa: E402
from contaflow.models import (  # noqa: E402
    AFP, ActivoFijo, ClaseDocumento, Cuenta, Documento, Empresa, Indicador, RegimenTributario,
    TipoCompra, TipoComprobante, TipoContrato, TipoSalud, Trabajador,
)
from contaflow.services import activofijo as af  # noqa: E402
from contaflow.services.contabilidad import (  # noqa: E402
    ErrorContable, LineaAsiento, balance_general, cerrar_ejercicio, crear_comprobante,
    estado_resultados, libro_mayor, saldos,
)
from contaflow.services.documentos import (  # noqa: E402
    calcular_iva, generar_asiento_documento, neto_desde_total, obtener_o_crear_entidad, totalizar,
)
from contaflow.services.formularios import generar_f22, generar_f29, guardar_f29  # noqa: E402
from contaflow.services.remuneraciones import (  # noqa: E402
    EntradaLiquidacion, calcular_liquidacion, centralizar_remuneraciones, guardar_liquidacion,
    impuesto_unico,
)
from contaflow.services.seed import cuenta_parametro, sembrar_empresa, sembrar_globales  # noqa: E402
from contaflow.services.utils import (  # noqa: E402
    digito_verificador, formatear_rut, formato_moneda, normalizar_rut, pesos, rut_valido,
)


class BaseTest(unittest.TestCase):
    """Crea una empresa limpia con su plan de cuentas para cada test."""

    contador = 0

    def setUp(self):
        crear_esquema()
        self.db = SessionLocal()
        sembrar_globales(self.db)
        BaseTest.contador += 1
        # RUT distinto por test para no chocar con la restricción de unicidad.
        cuerpo = str(76000000 + BaseTest.contador)
        rut = f"{cuerpo}-{digito_verificador(cuerpo)}"
        self.empresa = Empresa(
            rut=rut, razon_social=f"Empresa de Prueba {BaseTest.contador}",
            regimen=RegimenTributario.ART14D3, tasa_ppm=0.5,
        )
        self.db.add(self.empresa)
        self.db.commit()
        sembrar_empresa(self.db, self.empresa)

    def tearDown(self):
        self.db.close()

    def cuenta(self, codigo: str) -> Cuenta:
        from sqlalchemy import select

        return self.db.scalar(
            select(Cuenta).where(
                Cuenta.empresa_id == self.empresa.id, Cuenta.codigo == codigo
            )
        )

    def indicadores(self, anio: int, mes: int):
        """Los indicadores son globales, así que se reutilizan entre tests."""
        from sqlalchemy import select

        existente = self.db.scalar(
            select(Indicador).where(Indicador.anio == anio, Indicador.mes == mes)
        )
        if existente is None:
            self.db.add(Indicador(
                anio=anio, mes=mes, uf=39000, utm=68000, uta=816000,
                ingreso_minimo=529000, ipc=0.4,
            ))
            self.db.commit()


class TestRUT(unittest.TestCase):
    def test_digito_verificador(self):
        self.assertEqual(digito_verificador("76086428"), "5")
        self.assertEqual(digito_verificador("11111111"), "1")

    def test_validacion(self):
        self.assertTrue(rut_valido("76.086.428-5"))
        self.assertTrue(rut_valido("760864285"))
        self.assertFalse(rut_valido("76.086.428-4"))
        self.assertFalse(rut_valido(""))
        self.assertFalse(rut_valido("abc"))

    def test_formato(self):
        self.assertEqual(formatear_rut("760864285"), "76.086.428-5")
        self.assertEqual(normalizar_rut("76.086.428-5"), "76086428-5")

    def test_dv_k(self):
        # Un RUT cuyo dígito verificador es K.
        self.assertTrue(rut_valido("6.375.871-K"))


class TestMontos(unittest.TestCase):
    def test_iva(self):
        self.assertEqual(calcular_iva(100000), 19000)
        self.assertEqual(calcular_iva(9999), 1900)   # redondeo comercial

    def test_neto_desde_total(self):
        self.assertEqual(neto_desde_total(119000), 100000)

    def test_totalizar(self):
        t = totalizar(neto=100000, exento=5000)
        self.assertEqual(t["iva"], 19000)
        self.assertEqual(t["total"], 124000)

    def test_totalizar_con_retencion(self):
        t = totalizar(neto=100000, retencion=19000)
        self.assertEqual(t["total"], 100000)

    def test_formato_moneda(self):
        self.assertEqual(formato_moneda(1234567), "$1.234.567")
        self.assertEqual(formato_moneda(-5000), "-$5.000")


class TestPlanCuentas(BaseTest):
    def test_se_crea_el_plan(self):
        from sqlalchemy import func, select

        total = self.db.scalar(
            select(func.count(Cuenta.id)).where(Cuenta.empresa_id == self.empresa.id)
        )
        self.assertGreater(total, 130)
        self.assertIsNotNone(self.cuenta("1.1.01.001"))
        self.assertIsNotNone(self.cuenta("2.1.03.001"))

    def test_jerarquia(self):
        hija = self.cuenta("1.1.01.001")
        self.assertEqual(hija.padre.codigo, "1.1.01")
        self.assertEqual(hija.nivel, 4)
        self.assertTrue(hija.imputable)
        self.assertFalse(self.cuenta("1.1.01").imputable)

    def test_cuentas_por_defecto(self):
        cuenta = cuenta_parametro(self.db, self.empresa.id, "cta_iva_debito")
        self.assertIsNotNone(cuenta)
        self.assertEqual(cuenta.codigo, "2.1.03.001")


class TestComprobantes(BaseTest):
    def test_asiento_cuadrado(self):
        comp = crear_comprobante(
            self.db, self.empresa.id,
            tipo=TipoComprobante.TRASPASO, fecha=date(2025, 3, 15), glosa="Aporte de capital",
            lineas=[
                LineaAsiento(cuenta_id=self.cuenta("1.1.01.003").id, debe=5_000_000),
                LineaAsiento(cuenta_id=self.cuenta("3.1.01.001").id, haber=5_000_000),
            ],
        )
        self.assertTrue(comp.cuadrado)
        self.assertEqual(comp.numero, 1)
        self.assertEqual(pesos(comp.total_debe), 5_000_000)

    def test_rechaza_descuadre(self):
        with self.assertRaises(ErrorContable) as ctx:
            crear_comprobante(
                self.db, self.empresa.id,
                tipo=TipoComprobante.TRASPASO, fecha=date(2025, 3, 1), glosa="Descuadrado",
                lineas=[
                    LineaAsiento(cuenta_id=self.cuenta("1.1.01.001").id, debe=1000),
                    LineaAsiento(cuenta_id=self.cuenta("3.1.01.001").id, haber=900),
                ],
            )
        self.assertIn("no cuadra", str(ctx.exception))

    def test_rechaza_cuenta_no_imputable(self):
        with self.assertRaises(ErrorContable):
            crear_comprobante(
                self.db, self.empresa.id,
                tipo=TipoComprobante.TRASPASO, fecha=date(2025, 3, 1), glosa="Cuenta de grupo",
                lineas=[
                    LineaAsiento(cuenta_id=self.cuenta("1.1.01").id, debe=1000),
                    LineaAsiento(cuenta_id=self.cuenta("3.1.01.001").id, haber=1000),
                ],
            )

    def test_numeracion_correlativa(self):
        for i in range(3):
            crear_comprobante(
                self.db, self.empresa.id,
                tipo=TipoComprobante.INGRESO, fecha=date(2025, 5, i + 1), glosa=f"Asiento {i}",
                lineas=[
                    LineaAsiento(cuenta_id=self.cuenta("1.1.01.001").id, debe=1000),
                    LineaAsiento(cuenta_id=self.cuenta("4.1.01.001").id, haber=1000),
                ],
            )
        comp = crear_comprobante(
            self.db, self.empresa.id,
            tipo=TipoComprobante.INGRESO, fecha=date(2025, 5, 20), glosa="Cuarto",
            lineas=[
                LineaAsiento(cuenta_id=self.cuenta("1.1.01.001").id, debe=1000),
                LineaAsiento(cuenta_id=self.cuenta("4.1.01.001").id, haber=1000),
            ],
        )
        self.assertEqual(comp.numero, 4)

    def test_choque_de_numeracion_da_error_de_negocio_no_500(self):
        """Simula la condición de carrera de P1-1: dos requests casi
        simultáneas leen el mismo "siguiente número" (acá, forzado con un
        mock) antes de que la primera termine de guardar. La segunda debe
        recibir un ErrorContable claro, no un IntegrityError crudo."""
        import contaflow.services.contabilidad as mod

        with mock.patch.object(mod, "siguiente_numero", return_value=99):
            crear_comprobante(
                self.db, self.empresa.id,
                tipo=TipoComprobante.INGRESO, fecha=date(2025, 7, 1), glosa="Primero",
                lineas=[
                    LineaAsiento(cuenta_id=self.cuenta("1.1.01.001").id, debe=1000),
                    LineaAsiento(cuenta_id=self.cuenta("4.1.01.001").id, haber=1000),
                ],
            )
            with self.assertRaises(ErrorContable) as ctx:
                crear_comprobante(
                    self.db, self.empresa.id,
                    tipo=TipoComprobante.INGRESO, fecha=date(2025, 7, 2), glosa="Choca con el primero",
                    lineas=[
                        LineaAsiento(cuenta_id=self.cuenta("1.1.01.001").id, debe=2000),
                        LineaAsiento(cuenta_id=self.cuenta("4.1.01.001").id, haber=2000),
                    ],
                )
        self.assertIn("Otro proceso", str(ctx.exception))
        # La sesión debe quedar utilizable después del rollback interno.
        self.assertTrue(self.db.is_active)

    def test_mayor_y_saldo(self):
        for monto in (100_000, 250_000):
            crear_comprobante(
                self.db, self.empresa.id,
                tipo=TipoComprobante.INGRESO, fecha=date(2025, 6, 10), glosa="Venta",
                lineas=[
                    LineaAsiento(cuenta_id=self.cuenta("1.1.01.001").id, debe=monto),
                    LineaAsiento(cuenta_id=self.cuenta("4.1.01.001").id, haber=monto),
                ],
            )
        anterior, filas = libro_mayor(
            self.db, self.empresa.id, self.cuenta("1.1.01.001").id,
            date(2025, 6, 1), date(2025, 6, 30),
        )
        self.assertEqual(anterior, 0)
        self.assertEqual(len(filas), 2)
        self.assertEqual(pesos(filas[-1][1]), 350_000)


class TestCierreDeEjercicio(BaseTest):
    """P2-3: cerrar_ejercicio no impedía un segundo cierre para el mismo año."""

    def _con_resultado(self, anio=2025):
        crear_comprobante(
            self.db, self.empresa.id,
            tipo=TipoComprobante.INGRESO, fecha=date(anio, 3, 1), glosa="Venta",
            lineas=[
                LineaAsiento(cuenta_id=self.cuenta("1.1.01.001").id, debe=1_000_000),
                LineaAsiento(cuenta_id=self.cuenta("4.1.01.001").id, haber=1_000_000),
            ],
        )

    def test_primer_cierre_funciona(self):
        self._con_resultado()
        comp = cerrar_ejercicio(
            self.db, self.empresa.id, 2025, self.cuenta("3.1.01.001").id, usuario="prueba"
        )
        self.assertEqual(comp.tipo, TipoComprobante.CIERRE)
        self.assertTrue(comp.cuadrado)

    def test_segundo_cierre_del_mismo_anio_se_rechaza(self):
        self._con_resultado()
        cerrar_ejercicio(self.db, self.empresa.id, 2025, self.cuenta("3.1.01.001").id)

        # Aunque haya movimientos nuevos que cerrar, no debe generarse un
        # segundo comprobante de cierre para el mismo año.
        self._con_resultado()
        with self.assertRaises(ErrorContable) as ctx:
            cerrar_ejercicio(self.db, self.empresa.id, 2025, self.cuenta("3.1.01.001").id)
        self.assertIn("ya tiene un cierre", str(ctx.exception))

    def test_anos_distintos_no_interfieren(self):
        self._con_resultado(anio=2025)
        self._con_resultado(anio=2026)
        cerrar_ejercicio(self.db, self.empresa.id, 2025, self.cuenta("3.1.01.001").id)
        # El cierre de 2025 no debe bloquear el de 2026.
        comp_2026 = cerrar_ejercicio(self.db, self.empresa.id, 2026, self.cuenta("3.1.01.001").id)
        self.assertEqual(comp_2026.anio, 2026)

    def test_un_cierre_anulado_permite_uno_nuevo(self):
        from contaflow.services.contabilidad import anular_comprobante

        self._con_resultado()
        primero = cerrar_ejercicio(self.db, self.empresa.id, 2025, self.cuenta("3.1.01.001").id)
        anular_comprobante(self.db, primero, "Rehacer el cierre")

        self._con_resultado()  # el reverso del anulado deja saldos en 0; se agrega otro movimiento
        segundo = cerrar_ejercicio(self.db, self.empresa.id, 2025, self.cuenta("3.1.01.001").id)
        self.assertNotEqual(segundo.id, primero.id)


class TestDocumentos(BaseTest):
    def _venta(self, neto=1_000_000, folio="1001", tipo=33, mes=7):
        entidad = obtener_o_crear_entidad(
            self.db, self.empresa.id, "76086428-5", "Cliente Ejemplo SpA", cliente=True
        )
        montos = totalizar(neto=neto)
        doc = Documento(
            empresa_id=self.empresa.id, clase=ClaseDocumento.VENTA, tipo_dte=tipo, folio=folio,
            fecha_emision=date(2025, mes, 10), periodo_anio=2025, periodo_mes=mes,
            entidad_id=entidad.id, entidad_rut=entidad.rut, entidad_nombre=entidad.razon_social,
            neto=montos["neto"], exento=montos["exento"], iva=montos["iva"], total=montos["total"],
        )
        self.db.add(doc)
        self.db.commit()
        return doc

    def _compra(self, neto=500_000, folio="A-1", tipo=33, mes=7,
                tipo_compra=TipoCompra.DEL_GIRO):
        entidad = obtener_o_crear_entidad(
            self.db, self.empresa.id, "77777777-7", "Proveedor Ltda", proveedor=True
        )
        montos = totalizar(neto=neto)
        doc = Documento(
            empresa_id=self.empresa.id, clase=ClaseDocumento.COMPRA, tipo_dte=tipo, folio=folio,
            fecha_emision=date(2025, mes, 12), periodo_anio=2025, periodo_mes=mes,
            entidad_id=entidad.id, entidad_rut=entidad.rut, entidad_nombre=entidad.razon_social,
            neto=montos["neto"], exento=montos["exento"], iva=montos["iva"], total=montos["total"],
            tipo_compra=tipo_compra,
        )
        self.db.add(doc)
        self.db.commit()
        return doc

    def test_asiento_de_venta(self):
        doc = self._venta()
        comp = generar_asiento_documento(self.db, doc)
        self.assertTrue(comp.cuadrado)
        self.assertEqual(pesos(comp.total_debe), 1_190_000)

        por_cuenta = {m.cuenta.codigo: (pesos(m.debe), pesos(m.haber)) for m in comp.lineas}
        self.assertEqual(por_cuenta["1.1.02.001"], (1_190_000, 0))   # clientes al debe
        self.assertEqual(por_cuenta["4.1.01.001"], (0, 1_000_000))   # ventas al haber
        self.assertEqual(por_cuenta["2.1.03.001"], (0, 190_000))     # IVA débito al haber

    def test_asiento_de_compra(self):
        doc = self._compra()
        comp = generar_asiento_documento(self.db, doc)
        por_cuenta = {m.cuenta.codigo: (pesos(m.debe), pesos(m.haber)) for m in comp.lineas}
        self.assertEqual(por_cuenta["5.1.01.005"], (500_000, 0))     # compras al debe
        self.assertEqual(por_cuenta["1.1.04.001"], (95_000, 0))      # IVA crédito al debe
        self.assertEqual(por_cuenta["2.1.02.001"], (0, 595_000))     # proveedores al haber

    def test_nota_credito_invierte_el_asiento(self):
        doc = self._venta(neto=200_000, folio="NC-1", tipo=61)
        comp = generar_asiento_documento(self.db, doc)
        por_cuenta = {m.cuenta.codigo: (pesos(m.debe), pesos(m.haber)) for m in comp.lineas}
        # En una nota de crédito los clientes se abonan y las ventas se cargan.
        self.assertEqual(por_cuenta["1.1.02.001"], (0, 238_000))
        self.assertEqual(por_cuenta["4.1.01.001"], (200_000, 0))

    def test_compra_activo_fijo_usa_iva_credito_af(self):
        doc = self._compra(neto=1_000_000, folio="AF-1", tipo_compra=TipoCompra.ACTIVO_FIJO)
        comp = generar_asiento_documento(self.db, doc)
        codigos = {m.cuenta.codigo for m in comp.lineas}
        self.assertIn("1.1.04.002", codigos)   # IVA crédito activo fijo
        self.assertIn("1.2.01.004", codigos)   # activo fijo por defecto

    def test_regenerar_asiento_no_duplica(self):
        doc = self._venta()
        generar_asiento_documento(self.db, doc)
        generar_asiento_documento(self.db, doc)
        from sqlalchemy import func, select

        from contaflow.models import Comprobante, OrigenComprobante

        total = self.db.scalar(
            select(func.count(Comprobante.id)).where(
                Comprobante.origen == OrigenComprobante.VENTA,
                Comprobante.origen_id == doc.id,
            )
        )
        self.assertEqual(total, 1)


class TestFormulario29(TestDocumentos):
    def test_iva_a_pagar(self):
        self._venta(neto=1_000_000)                 # débito 190.000
        self._compra(neto=500_000)                  # crédito  95.000
        prop = generar_f29(self.db, self.empresa, 2025, 7)
        codigos = prop.como_dict()

        self.assertEqual(codigos["502"], 190_000)   # débitos de facturas emitidas
        self.assertEqual(codigos["520"], 95_000)    # crédito de facturas recibidas
        self.assertEqual(codigos["537"], 190_000)   # total débitos
        self.assertEqual(codigos["538"], 95_000)    # total créditos
        self.assertEqual(codigos["89"], 95_000)     # IVA determinado a pagar
        self.assertEqual(codigos["77"], 0)          # sin remanente
        self.assertEqual(prop.remanente_siguiente, 0)

    def test_remanente_cuando_credito_supera_debito(self):
        self._venta(neto=100_000)                   # débito  19.000
        self._compra(neto=1_000_000)                # crédito 190.000
        prop = generar_f29(self.db, self.empresa, 2025, 7)
        self.assertEqual(prop.remanente_siguiente, 171_000)
        self.assertEqual(prop.como_dict()["77"], 171_000)
        self.assertEqual(prop.total_a_pagar, prop.como_dict()["62"])  # sólo PPM

    def test_ppm_sobre_ventas_netas(self):
        self._venta(neto=2_000_000)
        prop = generar_f29(self.db, self.empresa, 2025, 7)
        codigos = prop.como_dict()
        self.assertEqual(codigos["563"], 2_000_000)
        self.assertEqual(codigos["62"], 10_000)     # 0,5% de 2.000.000

    def test_nota_credito_rebaja_debitos(self):
        self._venta(neto=1_000_000, folio="1", tipo=33)
        self._venta(neto=200_000, folio="NC-9", tipo=61)
        prop = generar_f29(self.db, self.empresa, 2025, 7)
        codigos = prop.como_dict()
        self.assertEqual(codigos["510"], 38_000)    # IVA de la nota de crédito
        self.assertEqual(codigos["537"], 190_000 - 38_000)
        self.assertEqual(codigos["563"], 1_000_000 - 200_000)

    def test_remanente_encadenado_entre_meses(self):
        self._venta(neto=100_000, folio="V1", mes=7)
        self._compra(neto=1_000_000, folio="C1", mes=7)
        prop_julio = generar_f29(self.db, self.empresa, 2025, 7)
        guardar_f29(self.db, self.empresa.id, prop_julio)
        self.assertEqual(prop_julio.remanente_siguiente, 171_000)

        self._venta(neto=2_000_000, folio="V2", mes=8)
        prop_agosto = generar_f29(self.db, self.empresa, 2025, 8)
        self.assertEqual(prop_agosto.remanente_anterior, 171_000)
        self.assertEqual(prop_agosto.como_dict()["89"], 380_000 - 171_000)

    def test_boletas_van_al_codigo_111(self):
        self._venta(neto=100_000, folio="B1", tipo=39)
        prop = generar_f29(self.db, self.empresa, 2025, 7)
        codigos = prop.como_dict()
        self.assertEqual(codigos["110"], 1)
        self.assertEqual(codigos["111"], 19_000)
        self.assertEqual(codigos["502"], 0)


class TestInformes(TestDocumentos):
    def test_estado_resultados(self):
        self._venta(neto=3_000_000)
        self._compra(neto=1_000_000)
        for doc in self.db.query(Documento).all():
            generar_asiento_documento(self.db, doc)

        eerr = estado_resultados(self.db, self.empresa.id, date(2025, 1, 1), date(2025, 12, 31))
        self.assertEqual(pesos(eerr["total_ingresos"]), 3_000_000)
        self.assertEqual(pesos(eerr["total_costos"]), 1_000_000)
        self.assertEqual(pesos(eerr["margen_bruto"]), 2_000_000)
        self.assertEqual(pesos(eerr["resultado_neto"]), 2_000_000)

    def test_balance_cuadra(self):
        crear_comprobante(
            self.db, self.empresa.id,
            tipo=TipoComprobante.TRASPASO, fecha=date(2025, 1, 2), glosa="Capital inicial",
            lineas=[
                LineaAsiento(cuenta_id=self.cuenta("1.1.01.003").id, debe=10_000_000),
                LineaAsiento(cuenta_id=self.cuenta("3.1.01.001").id, haber=10_000_000),
            ],
        )
        self._venta(neto=1_000_000)
        for doc in self.db.query(Documento).all():
            generar_asiento_documento(self.db, doc)

        bg = balance_general(self.db, self.empresa.id, date(2025, 1, 1), date(2025, 12, 31))
        self.assertEqual(pesos(bg["descuadre"]), 0)
        self.assertEqual(pesos(bg["total_activo"]), pesos(bg["total_pasivo_patrimonio"]))

    def test_saldos_arrastran_periodo_anterior(self):
        crear_comprobante(
            self.db, self.empresa.id,
            tipo=TipoComprobante.TRASPASO, fecha=date(2025, 1, 5), glosa="Enero",
            lineas=[
                LineaAsiento(cuenta_id=self.cuenta("1.1.01.001").id, debe=500_000),
                LineaAsiento(cuenta_id=self.cuenta("3.1.01.001").id, haber=500_000),
            ],
        )
        filas = saldos(
            self.db, self.empresa.id,
            desde=date(2025, 2, 1), hasta=date(2025, 2, 28), inicio_ejercicio=date(2025, 1, 1),
        )
        caja = next(f for f in filas if f.cuenta.codigo == "1.1.01.001")
        self.assertEqual(pesos(caja.debe_anterior), 500_000)
        self.assertEqual(pesos(caja.saldo), 500_000)
        self.assertEqual(pesos(caja.debe), 0)


class TestRemuneraciones(BaseTest):
    def _trabajador(self, sueldo=1_000_000, **extra):
        from sqlalchemy import select

        afp = self.db.scalar(select(AFP).where(AFP.nombre == "MODELO"))
        datos = dict(
            empresa_id=self.empresa.id, rut="18765432-1", nombres="Ana", apellidos="Pérez",
            fecha_ingreso=date(2020, 3, 1), tipo_contrato=TipoContrato.INDEFINIDO,
            sueldo_base=sueldo, afp_id=afp.id, salud_tipo=TipoSalud.FONASA,
            gratificacion_legal=True, afecto_afc=True,
        )
        datos.update(extra)
        trabajador = Trabajador(**datos)
        self.db.add(trabajador)
        self.db.commit()
        return trabajador

    def test_impuesto_unico_tramo_exento(self):
        # 13,5 UTM con UTM = 68.000 → 918.000; por debajo no hay impuesto.
        self.assertEqual(impuesto_unico(900_000, 68_000), 0)

    def test_impuesto_unico_segundo_tramo(self):
        # 1.000.000 / 68.000 = 14,7 UTM → 4% con rebaja de 0,54 UTM.
        esperado = pesos(1_000_000 * 0.04 - 0.54 * 68_000)
        self.assertEqual(impuesto_unico(1_000_000, 68_000), esperado)

    def test_liquidacion_completa(self):
        self.indicadores(2025, 7)
        trabajador = self._trabajador(sueldo=1_000_000)
        liq = calcular_liquidacion(
            self.db, trabajador, 2025, 7, EntradaLiquidacion(dias_trabajados=30)
        )

        # Gratificación Art. 50: 25% del devengado, con tope 4,75 IMM / 12.
        tope = pesos(4.75 * 529_000 / 12)
        self.assertEqual(pesos(liq.gratificacion), min(250_000, tope))
        self.assertEqual(
            pesos(liq.total_imponible), 1_000_000 + pesos(liq.gratificacion)
        )
        # AFP Modelo 10,58% y salud 7%.
        self.assertEqual(pesos(liq.afp_monto), pesos(float(liq.total_imponible) * 0.1058))
        self.assertEqual(pesos(liq.salud_monto), pesos(float(liq.total_imponible) * 0.07))
        self.assertEqual(pesos(liq.afc_monto), pesos(float(liq.total_imponible) * 0.006))
        self.assertEqual(
            pesos(liq.liquido),
            pesos(liq.total_haberes) - pesos(liq.total_descuentos),
        )
        self.assertGreater(pesos(liq.costo_empresa), pesos(liq.total_haberes))

    def test_tope_imponible(self):
        self.indicadores(2025, 7)
        trabajador = self._trabajador(sueldo=10_000_000, gratificacion_legal=False)
        liq = calcular_liquidacion(self.db, trabajador, 2025, 7, EntradaLiquidacion())
        tope = pesos(87.8 * 39_000)
        self.assertEqual(pesos(liq.afp_monto), pesos(tope * 0.1058))
        self.assertEqual(pesos(liq.salud_monto), pesos(tope * 0.07))

    def test_dias_proporcionales(self):
        self.indicadores(2025, 7)
        trabajador = self._trabajador(sueldo=900_000, gratificacion_legal=False)
        liq = calcular_liquidacion(
            self.db, trabajador, 2025, 7, EntradaLiquidacion(dias_trabajados=15)
        )
        self.assertEqual(pesos(liq.sueldo_base), 450_000)

    def test_centralizacion_cuadra(self):
        self.indicadores(2025, 7)
        trabajador = self._trabajador()
        guardar_liquidacion(
            self.db, calcular_liquidacion(self.db, trabajador, 2025, 7, EntradaLiquidacion())
        )
        comp = centralizar_remuneraciones(self.db, self.empresa.id, 2025, 7)
        self.assertTrue(comp.cuadrado)
        self.assertGreater(pesos(comp.total_debe), 0)

    def test_falta_indicadores(self):
        trabajador = self._trabajador()
        with self.assertRaises(Exception) as ctx:
            calcular_liquidacion(self.db, trabajador, 2030, 1, EntradaLiquidacion())
        self.assertIn("indicadores", str(ctx.exception).lower())


class TestActivoFijo(BaseTest):
    def _activo(self, **extra):
        datos = dict(
            empresa_id=self.empresa.id, codigo="AF-001", nombre="Notebook",
            fecha_adquisicion=date(2025, 1, 20), valor_adquisicion=1_200_000,
            vida_util_meses=24,
        )
        datos.update(extra)
        activo = ActivoFijo(**datos)
        self.db.add(activo)
        self.db.commit()
        return activo

    def test_calendario_completo(self):
        activo = self._activo()
        filas = af.calendario_depreciacion(activo)
        self.assertEqual(len(filas), 24)
        # Empieza el mes siguiente al de la adquisición.
        self.assertEqual((filas[0].anio, filas[0].mes), (2025, 2))
        self.assertEqual(filas[0].monto, 50_000)
        self.assertEqual(filas[-1].acumulado, 1_200_000)
        self.assertEqual(filas[-1].valor_libro, 0)

    def test_depreciacion_acelerada(self):
        activo = self._activo(vida_util_meses=72, usa_acelerada=True)
        self.assertEqual(activo.vida_util_efectiva, 24)

    def test_valor_residual(self):
        activo = self._activo(valor_residual=200_000)
        filas = af.calendario_depreciacion(activo)
        self.assertEqual(filas[-1].acumulado, 1_000_000)
        self.assertEqual(filas[-1].valor_libro, 200_000)

    def test_contabiliza_depreciacion(self):
        self._activo()
        comp, registros = af.procesar_depreciacion_mensual(self.db, self.empresa.id, 2025, 3)
        self.assertIsNotNone(comp)
        self.assertTrue(comp.cuadrado)
        self.assertEqual(pesos(comp.total_debe), 50_000)
        self.assertEqual(len(registros), 1)

    def test_baja_con_utilidad(self):
        activo = self._activo()
        af.procesar_depreciacion_mensual(self.db, self.empresa.id, 2025, 2)
        comp = af.dar_de_baja(self.db, activo, date(2025, 3, 31), valor_venta=1_300_000)
        self.assertTrue(comp.cuadrado)
        self.assertTrue(activo.dado_de_baja)
        codigos = {m.cuenta.codigo for m in comp.lineas}
        self.assertIn("4.2.01.002", codigos)   # utilidad en venta de activo fijo


class TestFormulario22(TestDocumentos):
    def test_rli_desde_balance(self):
        self._venta(neto=10_000_000)
        self._compra(neto=4_000_000)
        for doc in self.db.query(Documento).all():
            generar_asiento_documento(self.db, doc)

        prop = generar_f22(self.db, self.empresa, 2025, agregados=500_000, ppm_pagados=200_000)
        self.assertEqual(prop.rli, 6_500_000)
        self.assertEqual(prop.impuesto_primera, pesos(6_500_000 * 0.25))
        self.assertEqual(prop.saldo, prop.impuesto_primera - 200_000)

    def test_perdida_tributaria(self):
        self._compra(neto=4_000_000)
        for doc in self.db.query(Documento).all():
            generar_asiento_documento(self.db, doc)
        prop = generar_f22(self.db, self.empresa, 2025)
        self.assertLess(prop.rli, 0)
        self.assertEqual(prop.impuesto_primera, 0)


class TestAplicacionWeb(unittest.TestCase):
    """Prueba de humo: las rutas principales responden."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from contaflow.app import crear_app

        cls.cliente = TestClient(crear_app())
        cls.cliente.post("/login", data={"username": "admin", "password": "admin"},
                         follow_redirects=False)
        # El admin sembrado exige cambiar la contraseña por defecto antes de
        # poder usar el resto del sistema (P1-4) — igual que haría cualquier
        # persona la primera vez que abre ContAll.
        cls.cliente.post("/configuracion/cambiar-password", data={
            "password_actual": "admin", "password_nueva": "una-clave-de-prueba-larga",
        }, follow_redirects=False)
        # El asistente de perfil (contaflow/services/perfiles.py) también se
        # responde una sola vez antes de poder usar el resto del sistema.
        # "contador" no tiene tope de empresas ni secciones ocultas — es el
        # que necesita esta clase, que crea empresas y recorre rutas de
        # todos los módulos.
        cls.cliente.post("/bienvenida", data={"perfil": "contador"}, follow_redirects=False)
        # Las pantallas necesitan una empresa activa con su plan de cuentas.
        cls.cliente.post("/empresas/guardar", data={
            "rut": "76086428-5", "razon_social": "Empresa Web SpA",
            "regimen": "ART14D3", "tasa_ppm": "0.5",
        }, follow_redirects=False)

    def test_login_requerido(self):
        from fastapi.testclient import TestClient

        from contaflow.app import app

        anonimo = TestClient(app)
        respuesta = anonimo.get("/", follow_redirects=False)
        self.assertEqual(respuesta.status_code, 303)
        self.assertEqual(respuesta.headers["location"], "/login")

    def test_salud(self):
        self.assertEqual(self.cliente.get("/salud").json()["estado"], "ok")

    def test_rutas_principales(self):
        rutas = [
            "/", "/empresas", "/empresas/nueva", "/contabilidad/comprobantes",
            "/contabilidad/comprobantes/nuevo", "/contabilidad/diario", "/contabilidad/mayor",
            "/contabilidad/balance", "/contabilidad/periodos", "/contabilidad/conciliacion",
            "/tributario/ventas", "/tributario/compras", "/tributario/documentos/ventas/nuevo",
            "/tributario/documentos/compras/nuevo", "/tributario/honorarios", "/tributario/f29",
            "/tributario/f22", "/maestros/cuentas", "/maestros/entidades",
            "/maestros/centros-costo", "/maestros/indicadores", "/remuneraciones/trabajadores",
            "/remuneraciones/liquidaciones", "/remuneraciones/libro", "/remuneraciones/finiquito",
            "/activo-fijo", "/informes/resultados", "/informes/balance-general",
            "/informes/analisis", "/configuracion/cuentas", "/configuracion/parametros",
            "/configuracion/usuarios", "/configuracion/respaldos",
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.cliente.get(ruta)
                self.assertEqual(respuesta.status_code, 200, f"{ruta} → {respuesta.status_code}")

    def test_flujo_completo_por_http(self):
        """Venta, boleta, compra y honorario registrados vía formulario web."""
        self.cliente.post("/seleccionar-periodo", data={"anio": 2025, "mes": 9},
                          follow_redirects=False)

        def mensajes() -> list[str]:
            import re

            return re.findall(r'class="aviso [^"]*">([^<]+)', self.cliente.get("/").text)

        self.cliente.post("/tributario/documentos/ventas/guardar", data={
            "tipo_dte": 33, "folio": "9001", "fecha_emision": "2025-09-10",
            "periodo_anio": 2025, "periodo_mes": 9, "entidad_rut": "77777777-7",
            "entidad_nombre": "Cliente HTTP", "modo_monto": "neto", "neto": "1000000",
            "exento": "0", "iva": "190000", "contabilizar": "on",
        }, follow_redirects=False)

        # Boleta: el monto se ingresa con IVA incluido y debe desglosarse solo.
        self.cliente.post("/tributario/documentos/ventas/guardar", data={
            "tipo_dte": 39, "folio": "12", "fecha_emision": "2025-09-11",
            "periodo_anio": 2025, "periodo_mes": 9, "entidad_rut": "6375871-K",
            "entidad_nombre": "Consumidor", "modo_monto": "total", "total_bruto": "119000",
            "exento": "0", "contabilizar": "on",
        }, follow_redirects=False)

        self.cliente.post("/tributario/documentos/compras/guardar", data={
            "tipo_dte": 33, "folio": "C-77", "fecha_emision": "2025-09-05",
            "periodo_anio": 2025, "periodo_mes": 9, "entidad_rut": "96509660-4",
            "entidad_nombre": "Proveedor HTTP", "modo_monto": "neto", "neto": "400000",
            "exento": "0", "iva": "76000", "tipo_compra": "DEL_GIRO", "contabilizar": "on",
        }, follow_redirects=False)

        # Esta ruta chocaba con /tributario/{ruta}/guardar antes de separar
        # los documentos bajo /tributario/documentos/.
        self.cliente.post("/tributario/honorarios/guardar", data={
            "tipo": "RECIBIDA", "numero": "500", "fecha": "2025-09-20",
            "entidad_rut": "13456789-9", "entidad_nombre": "Profesional HTTP",
            "bruto": "200000", "tasa": "14.5", "periodo_anio": 2025, "periodo_mes": 9,
        }, follow_redirects=False)
        self.assertNotIn("Sección no encontrada.", mensajes())

        from sqlalchemy import select

        from contaflow.database import SessionLocal
        from contaflow.models import Empresa
        from contaflow.services.contabilidad import balance_general
        from contaflow.services.formularios import generar_f29

        db = SessionLocal()
        empresa = db.scalar(select(Empresa).where(Empresa.rut == "76086428-5"))
        codigos = generar_f29(db, empresa, 2025, 9).como_dict()

        self.assertEqual(codigos["502"], 190_000)          # factura de venta
        self.assertEqual(codigos["111"], 19_000)           # boleta: 119.000 → IVA 19.000
        self.assertEqual(codigos["520"], 76_000)           # crédito de la compra
        self.assertEqual(codigos["537"], 209_000)
        self.assertEqual(codigos["89"], 209_000 - 76_000)  # IVA a pagar
        self.assertEqual(codigos["563"], 1_100_000)        # neto de ventas
        self.assertEqual(codigos["151"], 29_000)           # 200.000 × 14,5%

        bg = balance_general(db, empresa.id, date(2025, 1, 1), date(2025, 12, 31))
        self.assertEqual(pesos(bg["descuadre"]), 0)
        db.close()

    def test_rut_invalido_es_rechazado(self):
        respuesta = self.cliente.post("/tributario/documentos/ventas/guardar", data={
            "tipo_dte": 33, "folio": "X", "fecha_emision": "2025-09-10",
            "entidad_rut": "11111111-2", "entidad_nombre": "RUT malo",
            "modo_monto": "neto", "neto": "1000",
        }, follow_redirects=True)
        self.assertIn("no es válido", respuesta.text)

    def test_no_se_puede_seleccionar_una_empresa_inactiva(self):
        """P2-2: seleccionar_empresa no filtraba por Empresa.activa — un
        POST directo con el id de una empresa dada de baja la dejaba
        seleccionada igual."""
        from sqlalchemy import select

        from contaflow.database import SessionLocal
        from contaflow.models import Empresa

        db = SessionLocal()
        try:
            empresa = Empresa(rut="76222333-K", razon_social="Empresa Inactiva SpA",
                              regimen=RegimenTributario.ART14D3, activa=False)
            db.add(empresa)
            db.commit()
            empresa_id = empresa.id
        finally:
            db.close()

        respuesta = self.cliente.post("/seleccionar-empresa", data={"empresa_id": empresa_id},
                                      follow_redirects=True)
        self.assertIn("no encontrada o inactiva", respuesta.text)

        # Y el selector de arriba tampoco debe seguir mostrándola como activa.
        self.assertNotIn("Empresa Inactiva SpA", respuesta.text)

    def test_folio_duplicado_da_mensaje_claro_no_500(self):
        """P1-2: cargar el mismo folio dos veces (doble clic, el mismo Excel
        importado dos veces) debe dar un aviso de negocio, no una página de
        error 500 con un IntegrityError crudo."""
        self.cliente.post("/seleccionar-periodo", data={"anio": 2025, "mes": 10},
                          follow_redirects=False)
        datos = {
            "tipo_dte": 33, "folio": "DUP-1", "fecha_emision": "2025-10-05",
            "periodo_anio": 2025, "periodo_mes": 10, "entidad_rut": "77777777-7",
            "entidad_nombre": "Cliente Duplicado", "modo_monto": "neto", "neto": "500000",
            "exento": "0", "iva": "95000", "contabilizar": "on",
        }
        primera = self.cliente.post("/tributario/documentos/ventas/guardar", data=datos,
                                     follow_redirects=False)
        self.assertEqual(primera.status_code, 303)

        segunda = self.cliente.post("/tributario/documentos/ventas/guardar", data=datos,
                                     follow_redirects=True)
        self.assertEqual(segunda.status_code, 200)
        self.assertIn("Ya existe un documento", segunda.text)

        from sqlalchemy import select

        from contaflow.database import SessionLocal
        from contaflow.models import Documento, Empresa

        db = SessionLocal()
        try:
            empresa = db.scalar(select(Empresa).where(Empresa.rut == "76086428-5"))
            cantidad = db.scalar(
                select(Documento).where(
                    Documento.empresa_id == empresa.id, Documento.folio == "DUP-1"
                )
            )
            self.assertIsNotNone(cantidad)  # el primero sí quedó guardado
            todos = db.scalars(
                select(Documento).where(
                    Documento.empresa_id == empresa.id, Documento.folio == "DUP-1"
                )
            ).all()
            self.assertEqual(len(todos), 1, "no debe haber quedado un segundo documento duplicado")
        finally:
            db.close()

    def test_exportaciones(self):
        rutas = [
            "/contabilidad/diario?formato=pdf", "/contabilidad/diario?formato=xlsx",
            "/contabilidad/balance?formato=xlsx", "/tributario/libro/ventas?formato=xlsx",
            "/tributario/libro/compras?formato=csv", "/tributario/f29?formato=pdf",
            "/informes/resultados?formato=pdf", "/activo-fijo?formato=xlsx",
            "/remuneraciones/libro?formato=xlsx", "/maestros/cuentas?formato=csv",
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.cliente.get(ruta)
                self.assertEqual(respuesta.status_code, 200, f"{ruta} → {respuesta.status_code}")
                self.assertGreater(len(respuesta.content), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
