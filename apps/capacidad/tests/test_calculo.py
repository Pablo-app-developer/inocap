"""
Pruebas del motor de cálculo puro (sin BD).

Validan las fórmulas contra los números REALES de la hoja ENERO del Excel:
  - Cabecera 1:      citas_mes = 504, neto = 502
  - Cardiopulmonar:  citas_mes = 444   (fórmula a mano ((21×3)+15×2+18)×4)
  - Barranca:        citas_mes = 292, neto = 267
"""

from decimal import Decimal

from apps.capacidad.services import calculo as c

L = c.MODO_EXCEL_LEGACY
CAL = c.MODO_CALENDARIO


# --- Redondeo mitad-hacia-arriba (REDONDEAR de Excel, no banker's) --- #
class TestRedondeo:
    def test_medio_hacia_arriba(self):
        assert c.round_half_up("0.5") == 1
        assert c.round_half_up("1.5") == 2
        assert c.round_half_up("2.5") == 3  # banker's daría 2; Excel da 3
        assert c.round_half_up("2.4") == 2

    def test_citas_por_dia(self):
        assert c.citas_por_dia(Decimal("10.5"), Decimal("0.5")) == 21
        assert c.citas_por_dia(Decimal("4"), Decimal("0.5")) == 8

    def test_tiempo_estandar_cero_no_divide(self):
        assert c.citas_por_dia(Decimal("10"), Decimal("0")) == 0


# --- Método POR_HORAS --- #
class TestPorHoras:
    def test_cabecera1_legacy(self):
        dias = c.DiasMes(dias_lav=5, sabados=1, semanas=4)
        cd = c.citas_por_dia(Decimal("10.5"), Decimal("0.5"))
        cm = c.citas_mes_por_horas(citas_dia_lav=cd, citas_dia_sabado=cd, dias=dias, modo=L)
        assert cd == 21
        assert cm == 504  # ((21×5)+(21×1))×4

    def test_calendario_no_multiplica_por_semanas(self):
        # En calendario, dias_lav/sabados ya son totales del mes.
        dias = c.DiasMes(dias_lav=22, sabados=5, semanas=4)
        cm = c.citas_mes_por_horas(citas_dia_lav=21, citas_dia_sabado=21, dias=dias, modo=CAL)
        assert cm == 21 * 22 + 21 * 5  # 567


# --- Método PERSONALIZADO (Cardiopulmonar) --- #
class TestPersonalizado:
    def test_cardiopulmonar_legacy(self):
        # ((21×3) + 15×2 + 18) × 4 = 444
        dias = c.DiasMes(dias_lav=3, sabados=0, semanas=4)
        terminos = [c.Termino(30), c.Termino(18)]
        cm = c.citas_mes_por_horas(
            citas_dia_lav=21, citas_dia_sabado=21, dias=dias, terminos=terminos, modo=L
        )
        assert cm == 444

    def test_termino_mensual_no_se_multiplica(self):
        dias = c.DiasMes(dias_lav=0, sabados=0, semanas=4)
        cm = c.citas_mes_por_horas(
            citas_dia_lav=0, citas_dia_sabado=0, dias=dias,
            terminos=[c.Termino(10, c.PERIODICIDAD_MENSUAL)], modo=L,
        )
        assert cm == 10


# --- Método POR_DIA_SEMANA (municipales): citas por día × ocurrencias --- #
class TestPorDiaSemana:
    def test_barranca_por_dia(self):
        # Barranca: L16 M8 X16 J17 V16 (sáb/dom 0). Ocurrencias legacy = 4 c/u L–V.
        citas = (16, 8, 16, 17, 16, 0, 0)
        ocurrencias = (4, 4, 4, 4, 4, 4, 0)
        cm = c.citas_mes_por_dia(citas, ocurrencias)
        assert cm == 292  # 73 × 4

    def test_ocurrencias_reales_del_calendario(self):
        # Enero 2026: Lun(3, con festivo) Mar4 Mié4 Jue(4, con festivo) Vie5.
        citas = (16, 8, 16, 17, 16, 0, 0)
        ocurrencias = (3, 4, 4, 4, 5, 0, 0)
        cm = c.citas_mes_por_dia(citas, ocurrencias)
        # 48 + 32 + 64 + 68 + 80 = 292
        assert cm == 292

    def test_sabado_cuenta_ocurrencias(self):
        citas = (0, 0, 0, 0, 0, 7, 0)  # solo sábados, 7 citas
        assert c.citas_mes_por_dia(citas, (0, 0, 0, 0, 0, 5, 0)) == 35  # 5 sábados


# --- NETO (corrección acordada: incluye ajuste por sobreatención) --- #
class TestNeto:
    def test_neto_incluye_ajuste(self):
        total, neto = c.calcular_neto(
            100, 5, [c.Novedad(10, c.SIGNO_DESCONTAR), c.Novedad(3, c.SIGNO_SUMAR)]
        )
        assert total == 105  # citas_mes + ajuste
        assert neto == 98  # 105 - 10 + 3

    def test_diferencia_documentada_vs_excel(self):
        # Excel calculaba neto = citas_mes − descontar (ignoraba el ajuste).
        # Con ajuste != 0 el resultado difiere intencionalmente.
        _, neto_nuevo = c.calcular_neto(100, 5, [c.Novedad(10)])
        neto_excel = 100 - 10  # comportamiento viejo (H − K)
        assert neto_nuevo == 95
        assert neto_excel == 90
        assert neto_nuevo != neto_excel


# --- Orquestador completo --- #
class TestOrquestador:
    def test_cabecera1_completo(self):
        entrada = c.EntradaCapacidad(
            metodo="POR_HORAS",
            modo=L,
            dias=c.DiasMes(5, 1, 4),
            horas_dia_lav=Decimal("10.5"),
            horas_dia_sabado=Decimal("10.5"),
            tiempo_estandar_horas=Decimal("0.5"),
            novedades=[c.Novedad(2)],
        )
        r = c.calcular_capacidad(entrada)
        assert r.citas_dia_lav == 21
        assert r.citas_mes == 504
        assert r.neto == 502

    def test_cardiopulmonar_completo(self):
        entrada = c.EntradaCapacidad(
            metodo="PERSONALIZADO",
            modo=L,
            dias=c.DiasMes(3, 0, 4),
            horas_dia_lav=Decimal("10.5"),
            horas_dia_sabado=Decimal("10.5"),
            tiempo_estandar_horas=Decimal("0.5"),
            terminos=[c.Termino(30), c.Termino(18)],
        )
        r = c.calcular_capacidad(entrada)
        assert r.citas_mes == 444
        assert r.neto == 444
