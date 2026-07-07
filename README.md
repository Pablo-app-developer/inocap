# Capacidad Instalada — Instituto Neumológico del Oriente

Aplicación Django que reemplaza el Excel de cálculo de capacidad instalada. Genérica
para **múltiples unidades de negocio** (Laboratorio Pulmonar, Clínica de Sueño, Servicio
Médico, etc.) y con cálculo por **calendario real** (los días hábiles y sábados varían
según el mes/año, descontando festivos de Colombia).

## Stack

- Django 5 · PostgreSQL (SQLite por defecto en desarrollo/pruebas)
- Lógica de negocio en `services/` (funciones puras + adaptadores ORM), nunca en las vistas
- Pruebas con pytest / pytest-django

## Puesta en marcha

```bash
python -m venv .venv
.venv/Scripts/activate           # Windows (bash: source .venv/Scripts/activate)
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo --reset      # datos de ejemplo (ENERO Lab. Pulmonar)
python manage.py createsuperuser        # o usa admin/admin123 si ya se creó
python manage.py runserver
python -m pytest                        # 34 pruebas
```

Para PostgreSQL, copia `.env.example` a `.env` y define `DB_ENGINE=postgres` + variables `DB_*`.

Admin en `/admin/` — ya permite CRUD de unidades, sedes, salas, parámetros, capacidades
(con novedades/términos/patrones en línea) y festivos.

## Arquitectura

```
config/                       settings (SQLite dev / PostgreSQL por env)
apps/core/                    UnidadNegocio, Sede, Sala (+ método de cálculo)
apps/calendario/              Festivo, servicio de días hábiles, festivos_co (Colombia)
apps/capacidad/
    models.py                 ParametroMensual, CapacidadSala, Novedad,
                              TerminoAdicional, PatronDiaSemana, ResumenMensual
    services/calculo.py       MOTOR PURO (Decimal + ROUND_HALF_UP), sin ORM
    services/orm.py           adaptadores: modelo -> motor -> snapshot
    management/commands/seed_demo.py
    tests/                     pruebas de fórmulas e integración
```

## Modelo de datos (resumen)

- **UnidadNegocio** → catálogo (Laboratorio Pulmonar, …).
- **Sede** → catálogo global (Cabecera, Fosunab, Barranca, San Gil, Málaga). Las sedes se
  comparten entre unidades (fiel al archivo TABLAS).
- **Sala** → pertenece a (Unidad, Sede) y define `metodo_calculo`:
  - `POR_HORAS`: `citas/día = ROUND(horas_día / tiempo_estándar)`.
  - `POR_DIA_SEMANA`: citas/día por patrón de días (sedes municipales).
  - `PERSONALIZADO`: POR_HORAS con overrides + términos (ej. Cardiopulmonar).
- **ParametroMensual** (unidad+año+mes): `modo` (CALENDARIO | EXCEL_LEGACY), días L–V,
  sábados/semana, semanas/mes, min/hora, tiempo/cita.
- **CapacidadSala** (sala+mes): entradas (horas/día, tiempo estándar, ajuste, overrides) y
  snapshot calculado (citas_día, citas_mes, citas_mes_total, neto).
- **Novedad** (± citas), **TerminoAdicional** (personalizado), **PatronDiaSemana** (municipales).
- **ResumenMensual**: meta, atenciones realizadas, cumplimiento.

## Reglas de negocio (fórmulas verificadas contra el Excel)

```
citas/día         = ROUND_HALF_UP(horas_día / tiempo_estándar)

POR_HORAS / PERSONALIZADO
  EXCEL_LEGACY:  citas_mes = (cd_lav·dias_lav + cd_sab·sabados + Σ términos_sem)·semanas + Σ términos_mes
  CALENDARIO:    citas_mes = cd_lav·dias_lav_real + cd_sab·sabados_real + Σ términos_sem·semanas + Σ términos_mes

POR_DIA_SEMANA
  EXCEL_LEGACY:  citas_mes = (Σ dias·citas_día)·semanas + Σ sábados_mes
  CALENDARIO:    citas_mes =  Σ ocurrencias_reales·citas_día + Σ sábados_mes

citas_mes_total   = citas_mes + ajuste_sobreatención
NETO              = citas_mes_total − Σ novedades_descontar + Σ novedades_sumar
cumplimiento %    = atenciones_realizadas / meta_atenciones
```

El seed reproduce **exactamente** el TOTAL GENERAL del Excel de enero: **3771**.

## Supuestos y diferencias con el Excel

1. **NETO incluye el ajuste por sobreatención** (columna I). El Excel calculaba
   `neto = H − K` (usando *citas mes*, no *citas mes total*), ignorando el ajuste.
   Aquí `neto = (citas_mes + ajuste) − descontar + sumar`. **Diferencia intencional**;
   solo cambia el resultado cuando el ajuste ≠ 0 (en enero era 0, por eso coincide).
2. **Modo calendario real** (requisito del proyecto, ahora **default** del seed): en
   `CALENDARIO` se cuentan los días L–V y sábados reales del mes descontando festivos, en
   vez de los fijos 5/1/4. Por eso **meses con 4 o 5 sábados dan capacidades distintas**
   (ej. enero'26 tiene 5 sábados → Cabecera 1 = 525 = 504 + 21, vs. 504 en modo legacy).
   `python manage.py seed_demo --modo legacy` reproduce la paridad exacta con el Excel (total 3771);
   en calendario el total de enero es 3875.
3. **Fórmulas a mano por sala** (ej. Cardiopulmonar `((21×3)+15×2+18)×4 = 444`) se modelan
   con **overrides estructurados** (`override_dias_lav`, `override_sabados`) + `TerminoAdicional`,
   no con cadenas de fórmula. Las salas `PERSONALIZADO` se calculan **siempre como receta
   semanal (× semanas)**, incluso si la unidad está en modo CALENDARIO — así Cardiopulmonar
   sigue dando 444 y no lo afectan los días/festivos del mes. Solo `POR_HORAS` (y los patrones
   de `POR_DIA_SEMANA`) usan el conteo real del calendario.
4. **Sedes municipales** (Barranca, San Gil, Málaga) usan `POR_DIA_SEMANA`; el resto `POR_HORAS`.
5. **Festivos de Colombia** se generan por algoritmo (fijos + Ley Emiliani + Semana Santa),
   incluyendo la **Ley 2578 de 2026** (N. S. del Rosario de Chiquinquirá, 9-jul con Emiliani;
   en 2026 se observa el lunes 13-jul). Válido para cualquier año.
6. **Capa monetaria** (distribución por servicio, tarifas por entidad → "estándar de
   capacidad"/facturación) del Excel: **pendiente para una fase posterior** (ver hoja de ruta).
7. Las hojas del Excel referencian celdas distintas por mes (D87/J43/D94); la BD las
   normaliza, así que el RESUMEN se vuelve un agregado por unidad/mes/año.

## Hoja de ruta (fases)

- [x] **Fase 1** — Proyecto, modelos, migraciones, seed, admin.
- [x] **Fase 2** — Motor de cálculo + servicio de calendario + 34 pruebas.
- [x] **Fase 3** — UI (dashboard + vista mensual por sala/sede) con edición inline HTMX
      y recálculo. Diseño según `design-system/MASTER.md` (metodología ui-ux-pro-max:
      paleta médica, WCAG AA, modo claro/oscuro, focus visible, `prefers-reduced-motion`).
- [ ] **Fase 4** — Convenios: importación masiva CSV/Excel (~14.400 filas) + buscador filtrable.
- [ ] **Fase 5** — Dashboard anual (RESUMEN) + gráficos + export Excel/PDF.
- [ ] **Fase 6** — Capa monetaria (tarifas/facturación) y roles (admin, líder, consulta).
