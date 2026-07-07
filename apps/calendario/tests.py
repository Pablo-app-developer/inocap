"""
Pruebas del servicio de calendario (conteo de días hábiles).

Enero 2026 (1-ene = jueves):
  - Sábados: 3,10,17,24,31 -> 5
  - Domingos: 4,11,18,25   -> 4
  - Días L–V: 31 − 5 − 4   -> 22
Festivos de enero 2026: 1-ene (jueves) y 12-ene (lunes, Reyes) -> ambos L–V.
"""

from datetime import date

from apps.calendario.services import (
    contar_dias_habiles,
    contar_ocurrencias,
    parse_dias_semana,
)


class TestConteoDias:
    def test_enero_2026_sin_festivos(self):
        conteo = contar_dias_habiles(2026, 1)
        assert conteo.dias_lav == 22
        assert conteo.sabados == 5

    def test_enero_2026_descuenta_festivos_entre_semana(self):
        festivos = [date(2026, 1, 1), date(2026, 1, 12)]  # jueves y lunes
        conteo = contar_dias_habiles(2026, 1, festivos)
        assert conteo.dias_lav == 20  # 22 − 2
        assert conteo.sabados == 5  # sin cambios

    def test_festivo_en_sabado_reduce_sabados(self):
        festivos = [date(2026, 1, 3)]  # sábado
        conteo = contar_dias_habiles(2026, 1, festivos)
        assert conteo.dias_lav == 22
        assert conteo.sabados == 4

    def test_febrero_2026(self):
        # 2026 no es bisiesto -> febrero tiene 28 días. 1-feb = domingo.
        conteo = contar_dias_habiles(2026, 2)
        assert conteo.dias_lav == 20
        assert conteo.sabados == 4

    def test_capacidad_varia_entre_meses(self):
        """Requisito central: la capacidad cambia según los días del mes."""
        enero = contar_dias_habiles(2026, 1)
        febrero = contar_dias_habiles(2026, 2)
        assert enero.dias_lav != febrero.dias_lav

    def test_meses_con_4_y_5_sabados(self):
        """Hay meses de 5 sábados y meses de 4: el conteo lo refleja."""
        # 2026: enero, mayo, agosto, octubre tienen 5 sábados; el resto 4.
        assert contar_dias_habiles(2026, 1).sabados == 5  # enero
        assert contar_dias_habiles(2026, 5).sabados == 5  # mayo
        assert contar_dias_habiles(2026, 2).sabados == 4  # febrero
        assert contar_dias_habiles(2026, 4).sabados == 4  # abril

    def test_diferencia_5to_sabado_en_citas(self):
        """Un mes con 5 sábados produce más citas que uno de 4, a igualdad de lo demás."""
        from apps.capacidad.services import calculo as c

        citas_dia = 21
        ene = contar_dias_habiles(2026, 1)  # 5 sábados
        feb = contar_dias_habiles(2026, 2)  # 4 sábados
        cm_ene = c.citas_mes_por_horas(
            citas_dia_lav=citas_dia, citas_dia_sabado=citas_dia,
            dias=c.DiasMes(ene.dias_lav, ene.sabados, 4), modo=c.MODO_CALENDARIO,
        )
        cm_feb = c.citas_mes_por_horas(
            citas_dia_lav=citas_dia, citas_dia_sabado=citas_dia,
            dias=c.DiasMes(feb.dias_lav, feb.sabados, 4), modo=c.MODO_CALENDARIO,
        )
        # El 5º sábado aporta 21 citas extra (más el efecto de los días L–V).
        assert cm_ene != cm_feb


class TestOcurrencias:
    def test_lunes_miercoles_viernes_enero(self):
        # Lun: 5,12,19,26 (4) | Mié: 7,14,21,28 (4) | Vie: 2,9,16,23,30 (5) = 13
        n = contar_ocurrencias(2026, 1, [0, 2, 4])
        assert n == 13

    def test_descuenta_festivo(self):
        n = contar_ocurrencias(2026, 1, [0, 2, 4], [date(2026, 1, 12)])  # lunes
        assert n == 12


class TestParse:
    def test_parse(self):
        assert parse_dias_semana("0,2,4") == [0, 2, 4]
        assert parse_dias_semana("") == []


class TestFestivosColombia:
    def test_cantidad_2026(self):
        from apps.calendario.festivos_co import festivos_colombia

        fechas = [f for f, _ in festivos_colombia(2026)]
        assert len(fechas) == 19  # 18 tradicionales + 13-jul (Ley 2026)
        assert len(set(fechas)) == 19  # sin duplicados

    def test_reyes_trasladado_a_lunes(self):
        from apps.calendario.festivos_co import festivos_colombia

        reyes = [f for f, n in festivos_colombia(2026) if n == "Reyes Magos"][0]
        assert reyes == date(2026, 1, 12)
        assert reyes.weekday() == 0  # lunes

    def test_chiquinquira_2026_trasladado_a_lunes_13(self):
        # Ley 2578/2026: base 9-jul (jueves en 2026) + Emiliani -> lunes 13-jul.
        from apps.calendario.festivos_co import festivos_colombia

        chiq = [f for f, n in festivos_colombia(2026) if "Chiquinquir" in n]
        assert chiq == [date(2026, 7, 13)]

    def test_chiquinquira_no_existe_antes_de_2026(self):
        from apps.calendario.festivos_co import festivos_colombia

        assert not any("Chiquinquir" in n for _, n in festivos_colombia(2025))

    def test_chiquinquira_2027_regla_general(self):
        # 9-jul-2027 es viernes -> se traslada al lunes 12-jul.
        from apps.calendario.festivos_co import festivos_colombia

        chiq = [f for f, n in festivos_colombia(2027) if "Chiquinquir" in n]
        assert chiq == [date(2027, 7, 12)]

    def test_extra_13_julio_reduce_dias_habiles_julio(self):
        from apps.calendario.festivos_co import festivos_colombia

        festivos_jul = [f for f, _ in festivos_colombia(2026) if f.month == 7]
        # Julio 2026: 20-jul (Independencia) + 13-jul (nuevo) = 2 festivos entre semana.
        base = contar_dias_habiles(2026, 7)  # sin festivos
        con_festivos = contar_dias_habiles(2026, 7, festivos_jul)
        assert con_festivos.dias_lav == base.dias_lav - 2
