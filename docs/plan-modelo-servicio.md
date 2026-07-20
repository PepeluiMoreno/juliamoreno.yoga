# Modelo Servicio→Actividad→Clases + fix Agenda + soft-delete (y diseños de cierre y anulación)

## Contexto

Probando el modelo de la academia de Julia aparecen a la vez un **bug concreto** en la
Agenda y una **redefinición del modelo de datos** que el usuario quiere fijar bien.

**Bug detonante**: el 21 de julio se pudo grabar una clase puntual/aislada **sin hora de
inicio**, y esa clase **se saltó la validación de solapamiento** con la que ya ocupaba ese
día. El sistema ignoró la hora en vez de rechazar o proponer el primer hueco libre.

**Redefinición del modelo (decisión del usuario)** — se pasa de 3 a 4 niveles:

```
Servicio (QUÉ ofrece Julia: "Hatha yoga", atemporal) ── se_sigue_ofertando (cartera)
   │ 1:N
Actividad (una PROGRAMACIÓN del servicio en una extensión temporal: "Hatha, sep–dic 2026")
   │ 1:N                                              ── hasta, estado, franjas, aforo, cal_event_type_id
Clases (SESIONES: recurrentes de una actividad programada, o sueltas no programadas)
   │ 1:N
Reservas / asistentes  ── viven en Cal.diy (motor externo)
```

Hoy **Actividad hace dos trabajos**: identidad del servicio (título, texto, foto, nivel) y
programación temporal (estado, `hasta`, franjas, umbral, plazas, `cal_event_type_id`). El
refactor separa la identidad (sube a **Servicio**) de la programación (se queda en
**Actividad/temporada**). No existe hoy ninguna tabla/campo de "servicio" (confirmado); el
concepto solo aparece en marketing (`docs/altas-google-meta.md:42`) y la doc ya llama a
Actividad "el catálogo/la oferta" (`docs/funcionalidades/actividades-clases-agenda.md`).

**Dos fuentes de verdad (se respetan)**: NocoDB (base `Yoga`) gestiona
Servicios/Actividades/Clases/Agenda; **Cal.diy** (`/opt/docker/apps/cal.diy`) manda sobre
reservas/asistentes/aforo, enlazado por `cal_event_type_id`. Regla de oro: nunca escribir
reservas fuera del motor (`handlers/reservas.py:5-8`).

**Decisiones del usuario que simplifican el refactor**:
- **Identificadores por UUID**, se abandonan los slugs (fin de colisiones y del casado por
  título de `vincula_agenda.py`).
- **Los datos actuales no importan**: re-provisión desde cero + **seeding limpio** (2
  servicios, 2–3 actividades/temporadas, varias clases semanales, 8 alumnos inscritos).
- **Web pública**: el grid muestra **solo la temporada vigente** de cada servicio.

### Orden del trabajo
1. **Fix del bug de Agenda** — implementar ya, independiente del refactor.
2. **Refactor del modelo (entidad Servicio)** — diseñar e implementar; nueva columna
   vertebral.
3. **Soft-delete con papelera + estudio de impacto** — implementar sobre el nuevo modelo.
4. **Diseño del cierre mensual** — documentar, no implementar.
5. **Diseño de la anulación de reserva por el alumno** — documentar, no implementar.

---

## Parte 1 — Fix del bug de Agenda (IMPLEMENTADO ✅)

Hecho y verificado (lógica de `_primer_hueco` probada con 6 casos, incl. límites de holgura).
Cambios: `scripts/backend/handlers/agenda.py` (`_primer_hueco` + exigir hora en puntual +
`sugerencia_hora` en 422/409) y `sitio/admin/index.html` (`#ag-guardar` ofrece colocar el
hueco propuesto con confirmación). Pendiente: probar end-to-end en el panel real.

### Detalle original (referencia)

**Causa raíz** (working tree == producción, commit 5cce795):
- Frontend `sitio/admin/index.html:1655-1690` (`#ag-guardar`): al crear una puntual solo
  valida el título (1671); **nunca comprueba `hora_inicio`**. Abierto desde "+ Añadir clase
  este día" (`nuevaEnFecha`→`crearEnFecha(fecha,"")`→`abrirModalAgenda({hora_inicio:""})`,
  1256-1268), el `<input type="time">` queda vacío y se envía `hora_inicio:""`.
- Backend `scripts/backend/handlers/agenda.py:129-134` (`_crear`, rama puntual): solo exige
  `fecha`, no `hora_inicio`.
- Backend `agenda.py:88-92` (`_valida_holgura`): la línea 91 `if not f or ini is None:
  continue` hace que una candidata **sin hora se salte el control de solape** → "deja
  grabar aunque ya hay otra clase", y la fila queda con `hora_inicio` vacía.

**Solución**: exigir hora en la puntual y, cuando falte (o la hora pise otra clase),
**proponer el primer hueco libre** del día respetando `HOLGURA_MIN` (30 min).
- `agenda.py`: helper "primer hueco libre" reutilizando `_minutos`/`_hhmm`/`HOLGURA_MIN`
  (54-63, 51) y el agrupado `por_fecha` de `_valida_holgura` (78-86).
- `_crear` puntual: tras exigir `fecha`, exigir `hora_inicio`; si falta →
  `422 {"error":"…necesita hora de inicio","sugerencia_hora":"HH:MM"}`. Añadir
  `sugerencia_hora` también al `409` de solape (ya calcula la hora más temprana, 104-108).
- `sitio/admin/index.html`: en `#ag-guardar`, si la puntual no trae hora, no enviar y
  prerrellenar `#ag-hora-ini` con la sugerencia; en `abrirModalAgenda`/`crearEnFecha`,
  prerrellenar el primer hueco libre al abrir sin hora.

**Verificación**: (1) puntual sin tocar hora en día ocupado → no guarda vacío, sugiere
hueco; (2) puntual que pisa otra → 409 con `sugerencia_hora`, al aceptar guarda; (3)
puntual con hora libre → guarda bien; (4) en NocoDB `Agenda.hora_inicio` nunca vacío; (5)
Aplazar/Trasladar sin regresión (`_editar`, agenda.py:141-164).

---

## Parte 2 — Refactor del modelo: entidad Servicio (IMPLEMENTADO ✅ backend + panel)

**Estado**: backend (commit 02021d2) y panel (commit 1e228f1) hechos, en rama
`modelo-servicio`. El panel ya habla el nuevo modelo: vista de **Servicios** (identidad +
`se_sigue_ofertando`) con sus **Temporadas** anidadas; la Agenda asocia clases a temporadas
y las Sesiones filtran por servicio.

**Verificado**: backend con import + py_compile; panel con chequeo de ids duplicados/rotos
(ninguno) y balance de delimitadores idéntico al de antes del cambio. **NO probado contra
NocoDB real** — no hay acceso desde el entorno de trabajo ni runtime JS para validar el
script. Pendiente: ejecutar `provision-nocodb.py --seed-demo` y recorrer las vistas.

Hecho: tabla `Servicios` + `Actividades`-temporada + `Clases`/`Agenda`/`Reservas` en el
provisioner con UUIDs; seeding demo (`--seed-demo`, destructivo y aislado); `actividades.py`
partido en dos CRUDs; `build-web.py` pinta una tarjeta por servicio con su temporada
vigente; cruces por uuid en reservas/listas/sesiones/resumen/agenda/calcom; helper
`datos.servicios_por_uuid()`. `Clases`/`Agenda` conservan el campo `actividad_id` (su valor
pasa a ser el uuid de la temporada) para no renombrar por todo el código y el panel.

### Detalle de diseño (referencia)

### Esquema nuevo (`scripts/provision-nocodb.py`, dict `TABLAS` 26-48)

- **Tabla `Servicios`** (NUEVA): `uuid` (texto, PK lógica generada con `uuid.uuid4()` en
  Python — NocoDB conserva su `Id` numérico propio para los PATCH), `se_sigue_ofertando`
  (Checkbox), y los campos de **identidad** que hoy están en Actividades:
  `titulo_{es,en,fr,de}`, `texto_{es,en,fr,de}`, `foto`, `nivel`, `es_hash`, `revisado`.
- **Tabla `Actividades`** (temporada) — se replantea: `uuid`, `servicio_uuid` (FK al
  Servicio), y los campos de **programación temporal**: `estado`
  (`propuesta|programada|en_curso|finalizada`), `hasta`, `franjas`, `franjas_elegibles`,
  `umbral`, `plazas`, `visible`, `mostrar_contador`, `cal_event_type_id`, `precio`,
  `duracion`, `lugar` (estos tres pueden variar por temporada; `duracion` suele ser estable
  pero se deja en la temporada por simplicidad).
- **Clases** y **Agenda**: sus FKs `actividad_id` pasan a apuntar a la **temporada** por su
  `uuid` (renombrar a `actividad_uuid` para claridad). Recordatorio del inventario: estas
  dos tablas **no** están en `provision-nocodb.py` (se gestionan en NocoDB); el seeding las
  poblará por API igual que a las demás.

**UUIDs**: NocoDB no necesita un tipo especial — el `uuid` es un campo de texto poblado con
`uuid.uuid4()` en el seeding y en las altas (`handlers/*` al crear). Los cruces entre tablas
usan ese `uuid`; se abandona `util.slug` como clave (queda, si acaso, para textos legibles,
no para identidad). `scripts/vincula_agenda.py` (casado por título) queda **obsoleto** y se
retira o reescribe para casar por `uuid`.

### Re-provisión + seeding limpio

- Ampliar `provision-nocodb.py` para crear `Servicios` y la nueva `Actividades`, y **sembrar
  un dataset de demostración** (reutilizando el patrón "siembra solo si vacía",
  provision-nocodb.py:105-127): **2 Servicios** (p. ej. Hatha, Yoga +60), **2–3 Actividades**
  (temporadas colgando de esos servicios, con `hasta` futura y `se_sigue_ofertando=true`),
  **varias Clases** semanales adscritas, y **8 alumnos inscritos** por clase. Los alumnos
  reales viven en Cal.diy; para el seed se usa la copia ligera `Reservas` de NocoDB (y, si
  se quiere el aforo real, `calcom/alumnos_prueba.py` que ya existe para altas de prueba).
- Como los datos actuales son desechables, el seed puede correr sobre tablas vaciadas.

### Adaptación de handlers y web

- **`handlers/actividades.py`**: hoy un solo CRUD mezcla identidad + temporada
  (POST 47-85, PATCH 87-113). **Partir en dos**: CRUD de Servicios (identidad + cartera) y
  CRUD de Actividades/temporadas (programación, con `servicio_uuid`). Generar `uuid` al
  crear en vez de `slug(titulo)` (hoy en :53).
- **`build-web.py`**: el grid es plano, una tarjeta por Actividad (`seccion_actividades`
  163-296; volcado en `desde_nocodb` 407-476). Cambiar a **una tarjeta por Servicio con su
  temporada vigente**: para cada Servicio con `se_sigue_ofertando`, elegir su Actividad
  vigente (`visible`, no `_archivada`, `hasta` futura) y pintar identidad (del Servicio) +
  horarios/aforo (de la temporada). Los textos traducidos (DeepL, `es_hash`) pasan a
  colgar del Servicio (361-404).
- **`handlers/reservas.py`** (`_actividad_de`, `_ficha`, `_actividad`, 47-166): la ficha
  pública que ve el alumno combina identidad (Servicio) + datos de reserva (temporada vía
  `cal_event_type_id`). Ajustar los cruces a `servicio_uuid`/`actividad_uuid`.
- **`handlers/listas.py`, `sesiones.py`, `resumen.py`, `agenda.py`, `clases.py`,
  `calcom/alta_clases.py`, `calcom/enlaza_actividades.py`**: todos cruzan por el `id` de
  Actividad o por `cal_event_type_id`. Revisar uno a uno (inventario disponible) para que
  usen los `uuid` nuevos; `cal_event_type_id` permanece en la **temporada**, no sube al
  Servicio.
- **URLs públicas**: `/interes.html?actividad=<id>` (build-web.py:266,287) y
  `Interesados.actividad` (webhooks.py:39,45) pasan a llevar el `uuid` correspondiente
  (probablemente del Servicio, para que el interés sea por servicio, no por temporada — a
  fijar al implementar).

### Verificación del refactor
1. `provision-nocodb.py` sobre base limpia crea `Servicios` + `Actividades` y siembra el
   dataset demo sin error.
2. La web pública muestra **una tarjeta por servicio** (sin duplicados por temporada), con
   la temporada vigente.
3. Reservar/listar/ocupación siguen funcionando cruzando por `uuid` + `cal_event_type_id`.
4. Alta de clases en Cal.diy (`alta_clases.py`) sigue enlazando la temporada correcta.

---

## Parte 3 — Soft-delete con papelera + estudio de impacto (IMPLEMENTADO ✅)

**Estado**: hecho en commit `fab175e` (rama `modelo-servicio`). Columnas
`eliminado`/`eliminado_fecha` en todas las tablas; filtro en `nocolib.records` (cubre los 8
puntos de lectura directa, incluido `build-web.py`); `datos.borra*` en soft por defecto con
`definitivo=True` para purgar, más `restaura()`/`papelera()`; handler nuevo
`handlers/papelera.py` (`/admin/api/papelera`, `/restaurar`, `/purgar`, `/admin/api/impacto`);
DELETE en los CRUD de Servicios y Temporadas; veto de la agenda trasladado al borrado
definitivo; panel con modal de impacto + casilla "Borrado definitivo" y vista Papelera.
Verificado: compile+import del backend, prueba unitaria del filtrado y del cálculo de
impacto, ids/balance del panel. **No probado contra NocoDB real.**

### Detalle de diseño (referencia)

**Requisito**: en el panel Julia **siempre** puede eliminar objetos. Borrado = **soft-delete**
por defecto (oculto pero recuperable desde una **Papelera**); solo se borra de verdad si en
la modal se marca **"Borrado definitivo"**.

**Modelo (columna por tabla)**: añadir a cada tabla de `Yoga` `eliminado` (Checkbox) y
`eliminado_fecha` (DateTime), idempotente en `provision-nocodb.py` (patrón de columnas
96-103). Cubrir también `Servicios`, `Agenda`, `Clases`, `Reservas` (que no están en el
dict `TABLAS`) con un paso que recorra todas las tablas resueltas.

**Intercepción de borrado — `scripts/backend/datos.py`**: `borra`/`borra_varios` (66-74)
pasan a soft-delete por defecto (PATCH `eliminado=true` + `eliminado_fecha`); parámetro
`definitivo=True` hace el DELETE real. Nueva `restaura(tabla, rid)`.

**Intercepción de lectura — DOS niveles** (el inventario confirma que `datos.lee` no basta:
hay 8 lecturas directas a `nocolib.records`, y `build-web.py:451` es por donde un eliminado
se colaría en la web pública):
- **`scripts/nocolib.py:69-71` `records(...)`**: añadir filtro que **excluya `eliminado=true`
  por defecto**, con opt-in para incluirlos. Así lo heredan `datos.lee`, `build-web.py` y
  `calcom/` a la vez.
- **`datos.lee(tabla, incluir_eliminados=False)`**: la Papelera activa el opt-in.
- **Excepción** `provision-nocodb.py:106/114/122` (chequeo "¿tabla vacía?"): usar opt-in de
  incluir eliminados para no dar falso "vacía".

**Estudio de impacto en la modal** (requisito del usuario): endpoint
`GET /admin/api/impacto?tabla=&uuid=` que cuenta dependencias por las relaciones del modelo.
Con el nuevo modelo el caso importante es **Servicio** (maestra de referencia): cuenta sus
Actividades/temporadas, y por ellas las Clases, Agenda y Reservas. La modal muestra qué
arrastra antes de confirmar.

**Cartera vs borrado (ejes ortogonales)**: `se_sigue_ofertando` (en Servicio) retira de la
oferta **sin borrar ni perder historial** — es la vía normal para "ya no doy esto". El
borrado (incluso soft) es la excepción; el **borrado definitivo** de un Servicio con
historial se **bloquea** mientras existan temporadas/clases/reservas no purgadas (se
propone bloquear por defecto; el soft-delete siempre permitido).

**Reconciliar con la regla actual de Agenda** (agenda.py:174-186): hoy `_eliminar` niega
borrar una clase visible o de actividad en curso. Con soft-delete recuperable ese veto
aplica solo al **borrado definitivo**; el soft-delete de una ocurrencia se permite siempre.

**UI (`sitio/admin/index.html`)**: modal de borrado con (a) estudio de impacto, (b) opción
"Retirar de la cartera" (`se_sigue_ofertando=false`) cuando aplica a un Servicio, (c)
checkbox "Borrado definitivo" (desmarcado por defecto); control de `se_sigue_ofertando` en
la ficha de Servicio; **vista Papelera** con Restaurar / Borrar definitivamente. Endpoints
`GET /admin/api/papelera`, `POST .../restaurar`, `POST .../purgar`.

**Verificación**: (1) borrar sin marcar → va a Papelera, desaparece de panel y web, no rompe
lecturas; (2) restaurar → vuelve intacto; (3) borrado definitivo → desaparece de NocoDB y
Papelera; (4) `build-web.py` no publica soft-borrados; (5) definitivo de Servicio con
historial → bloqueado; (6) retirar de cartera → sale del grid, historial intacto.

---

## Parte 4 — Diseño del cierre MENSUAL de producción (no implementar aún)

Cuadre **mensual** (no por sesión) que agrega las clases impartidas en el mes para no perder
el registro de "producción" y cuadrar **horas trabajadas e ingresos**. Las clases puntuales
aisladas sin `cal_event_type_id` tienen alumnos **no pregrabados** que se registran a
posteriori.

- Recorrer `Agenda` del mes (puntuales + recurrentes materializadas), excluyendo
  `estado=cancelada`. De cada ocurrencia salen **fecha, hora, duración → horas trabajadas**.
- Clases **con `cal_event_type_id`**: asistentes consultables desde Cal.diy reutilizando
  `handlers/listas.py:58-101` y `sesiones.py`.
- Clases puntuales **sin event-type**: hoy no hay dónde anotar asistentes reales. Opción:
  campos nuevos en `Agenda` (`asistentes_reales`, `importe`, `cerrada`) rellenados en la
  vista de cierre (se quedan en NocoDB porque nunca pasaron por el motor), o una tabla
  `Cierres` mensual. **A decidir antes de implementar.**
- **Ingresos**: cruzar concepto/asistentes con `Precios` (`handlers/precios.py`).
- **Salida**: vista "Cierre del mes" en el panel (clases del mes, horas totales, asistentes,
  importe; lo pendiente de registrar resaltado), en la línea de Agenda/Sesiones/Tarifas.

**Pendiente**: dónde persistir asistentes/importe de clases sin event-type; si el cierre es
informe (solo lectura) o registro (editable).

---

## Parte 5 — Diseño de la anulación de reserva por el alumno (no implementar aún)

Un alumno puede **anular su reserva hasta un tiempo antes** de la clase; esa **antelación
mínima es un parámetro por Actividad/temporada** (cada una fija su margen).

- **Parámetro nuevo**: campo `cancelacion_horas` (Number) en **Actividades/temporada** (es
  propiedad de la programación, no del Servicio). Vacío/0 = sin restricción o valor por
  defecto.
- **Cancelación en el motor**: reutilizar `cliente.cancelar_reserva(uid, motivo)`
  (`calcom/cliente.py:158-161`); tras cancelar, actualizar la copia `Reservas` y
  `dispara_rebuild()` (como `_reservar`, reservas.py:274-282).
- **Endpoints públicos nuevos** (patrón `handlers/reservas.py`, ruta pública sin Authelia):
  - `GET /mis-reservas?email=…` → reservas **futuras** del alumno (Cal.diy `cliente.bookings`
    × copia NocoDB por email); marca cuáles siguen siendo anulables (`inicio` vs
    `ahora + cancelacion_horas`).
  - `POST /anular {uid,email}` → revalida en servidor la antelación; si procede, cancela; si
    no, `409` con mensaje claro.
- **Identidad = por email** (decisión del usuario). **Privacidad a resolver al implementar**:
  buscar por email sin verificar expone reservas ajenas; valorar magic link de confirmación
  o limitar la info. La regla `listas.py:4-6` (datos personales protegidos) obliga a cuidarlo.
- **UI del alumno**: página pública donde introduce email, ve próximas clases y anula las que
  estén en plazo; las fuera de plazo, deshabilitadas con el motivo.

**Pendiente**: verificación del email (magic link vs. directo), valor por defecto de
`cancelacion_horas`, y si Julia puede anular en nombre del alumno desde el panel.
