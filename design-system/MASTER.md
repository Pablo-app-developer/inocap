# Sistema de diseño — Capacidad Instalada (INO)

Guía única de diseño para la UI, siguiendo la metodología de `ui-ux-pro-max-skill`
(estilo + paleta por industria + tipografía + efectos + anti-patrones + checklist).
Las páginas pueden sobrescribir puntos concretos en `design-system/pages/*.md`.

## Contexto / industria
Herramienta interna de **salud** (institución neumológica) para gestión de
**capacidad instalada**: pantallas de **datos densos** (tablas de salas, totales,
indicadores). No es marketing; prima claridad, legibilidad y confianza.

## Estilo
- **Minimal + Executive/Data-Dense Dashboard.** Superficies limpias, jerarquía por
  tipografía y espacio, tablas legibles, tarjetas KPI sobrias.
- Bordes sutiles, esquinas redondeadas moderadas, sombras suaves (no pesadas).

## Paleta (mood médico: calmado, confiable) — WCAG AA
| Rol | Claro | Oscuro |
|-----|-------|--------|
| Brand / Primary | `#0B6E99` | `#38BDF8` |
| Primary strong | `#075985` | `#0EA5E9` |
| Accent (teal) | `#0D9488` | `#2DD4BF` |
| Éxito | `#15803D` | `#4ADE80` |
| Advertencia | `#B45309` | `#FBBF24` |
| Peligro | `#B91C1C` | `#F87171` |
| Fondo | `#F8FAFC` | `#0F172A` |
| Superficie | `#FFFFFF` | `#1E293B` |
| Borde | `#E2E8F0` | `#334155` |
| Texto | `#0F172A` | `#E2E8F0` |
| Texto tenue | `#64748B` | `#94A3B8` |

Contraste texto/fondo ≥ 4.5:1. El color nunca es el único portador de significado
(se acompaña de texto/íconos).

## Tipografía
- Familia: stack de sistema (`-apple-system, "Segoe UI", Roboto, Helvetica, Arial`),
  cero dependencias de red; realce opcional con **Inter** si hay conexión.
- Escala: título 1.5–1.75rem, subtítulo 1.125rem, cuerpo 0.95rem, meta 0.8rem.
- Números tabulares (`font-variant-numeric: tabular-nums`) en tablas de cifras.

## Espaciado y layout
- Escala base 4px (0.25rem). Contenedores con `max-width` y padding responsivo.
- **Mobile-first.** Breakpoints: 375 / 768 / 1024 / 1440.
- Tablas anchas con scroll horizontal contenido (`overflow-x:auto`), nunca desbordan el body.

## Efectos e interacción
- Transiciones 150–250ms (`ease`), solo en color/sombra/transform.
- Estados hover en filas y controles; `cursor: pointer` en interactivos.
- **Focus visible** siempre (anillo de 2px con color brand). Navegación por teclado.
- Respeta `prefers-reduced-motion: reduce` (desactiva animaciones).

## Anti-patrones (evitar)
- Neón, degradados morado/rosa "AI", sombras duras, animaciones bruscas.
- Tablas sin encabezado fijo ni alineación numérica.
- Color como único indicador de estado (cumplimiento, alertas).

## Checklist pre-entrega
- [ ] Contraste ≥ 4.5:1 en texto; estados hover/focus/disabled definidos.
- [ ] Responsive verificado a 375 / 768 / 1024 / 1440.
- [ ] `prefers-reduced-motion` respetado; foco visible; navegable por teclado.
- [ ] Modo claro y oscuro correctos.
- [ ] Cifras con `tabular-nums` y alineadas a la derecha.
