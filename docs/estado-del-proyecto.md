# Estado del proyecto — julio 2026

Este documento recoge lo que hay que saber para retomar el trabajo sin haber
estado en la conversación donde se decidió. Es el contexto que no se deduce
leyendo el código.

## El modelo de datos, en cuatro niveles

```
Servicio ── lo que Julia enseña ("Hatha yoga"). ATEMPORAL.
   │        Su nombre, descripción, nivel, foto y la tarifa por hora.
   │        `se_sigue_ofertando` dice si está en la cartera vigente.
   │ 1:N
Actividad ─ una PROGRAMACIÓN de ese servicio en un tramo de tiempo.
   │        `periodo` es cómo lo llama Julia ("Campaña de verano", "Otoño"),
   │        texto libre. `desde`/`hasta` acotan, `horario` es su semana tipo.
   │ 1:N
Clases ──── la semana tipo desglosada (tabla Clases) y cada ocurrencia
   │        concreta (tabla Agenda), con su fecha, estado y motivo.
   │ 1:N
Reservas ── quién viene. La fuente de verdad es Cal.diy; en NocoDB hay una
            copia ligera con el teléfono.
```

**Por qué así.** "Actividad" hacía dos trabajos a la vez: era la identidad de lo
que se enseña y a la vez una programación concreta. Eso obligaba a repetir la
descripción entera cada temporada y hacía imposible retirar algo de la cartera
sin perder su historial. Separarlos fue el refactor grande de julio.

**Identificadores: UUID, no slugs.** Se abandonaron los slugs derivados del
título porque dos temporadas del mismo servicio colisionaban. `util.slug` ya no
se usa como clave. NocoDB mantiene además su `Id` numérico, que es el que viaja
en los PATCH y DELETE.

**Ojo:** `Clases.actividad_id` y `Agenda.actividad_id` conservan ese nombre pero
su valor es el **uuid de la actividad**, no un slug. Se dejó así para no
renombrar por todo el código.

## Dos fuentes de verdad

- **NocoDB** (base `Yoga`) manda sobre la gestión: servicios, actividades,
  clases, agenda, lugares, precios.
- **Cal.diy** (fork MIT de Cal.com, en `/opt/docker/apps/cal.diy`, fuera de este
  repo) manda sobre reservas, asistentes y aforo. El puente es
  `Actividades.cal_event_type_id`.

**Regla de oro del repo:** las reservas SIEMPRE las escribe Cal.diy. El backend
lee su API y guarda copia; nunca escribe reservas por su cuenta.

Hoy **ninguna actividad está enlazada** con Cal.diy (`cal_event_type_id = 0`),
así que las vistas que dependen de él (Sesiones, aforo real) no tienen datos. El
Panel de control se alimenta de NocoDB por eso.

## Ciclo de vida de una actividad

```
propuesta ──(llega al umbral de interesados)──▶ programada
programada ──(Julia pulsa "Ofertar")──▶ prevista ──(llega la fecha)──▶ en curso
                              └──(si ya empezó)──▶ en curso
suspendida ◀──(Suspender, con motivo)── cualquiera ──▶ finalizada (Cancelar)
```

Las flechas automáticas se resuelven **al leer las actividades**
(`handlers/actividades.py:_transiciones`), no con una tarea de fondo: así lo que
Julia ve al abrir el panel está al día. Solo se escribe en NocoDB lo que cambia.

## Decisiones tomadas que no se ven en el código

- **Borrar es reversible.** Todo borrado es lógico (`eliminado` +
  `eliminado_fecha`) y va a la Papelera. Solo el checkbox "Borrado definitivo"
  saca la fila de NocoDB. El filtro vive en `nocolib.records`, la primitiva por
  la que pasan backend, `build-web.py` y los scripts de calcom: ponerlo ahí
  evita que una fila borrada se cuele en la web por olvidar un filtro.
- **Retirar de la cartera ≠ borrar.** Para dejar de ofrecer algo está
  `se_sigue_ofertando`, que conserva el historial. Antes de borrar, la modal
  enseña qué arrastra (`/admin/api/impacto`).
- **El lugar condiciona la planificación.** `aforo` limita las plazas y
  `disponibilidad` las horas, y se comprueban en los DOS niveles: el calendario
  semanal de la actividad y la clase suelta de la agenda.
- **El motivo puede ser público o no.** Julia decide en cada acción si se cuenta
  en la web (`motivo_publico`). Marcado por defecto al trasladar, desmarcado al
  suspender o cancelar.

## Cómo se prueba esto

**No hay tests automatizados.** Lo que hay:

- `python3 scripts/provision-nocodb.py` — crea tablas y columnas que falten.
  Idempotente, no borra nada.
- `python3 scripts/provision-nocodb.py --seed-demo` — **DESTRUCTIVO**: vacía el
  modelo de oferta y siembra un dataset de prueba (8 servicios, 9 actividades,
  85 clases con incidencias, 215 reservas de 15 alumnos de seis países, 11
  interesados, 2 filas en la papelera). Está hecho para que se vea trabajar la
  aplicación, no para ser bonito: incluye canceladas, aplazadas, un servicio
  retirado y una temporada caducada.
- **El JS del panel se valida con el node del contenedor de Cal.diy**, que no hay
  otro en la máquina:
  ```
  docker cp panel.js caldiy-calcom-1:/tmp/panel.js
  docker exec caldiy-calcom-1 node --check /tmp/panel.js
  ```
  Contar llaves no vale: un identificador repetido es un SyntaxError que aborta
  el script entero y deja la página en blanco. Ya pasó.
- **Comprobar también que cada clase CSS usada tenga su regla.** Un `.clase` sin
  estilo no da error en ninguna parte y descuadra la página. También pasó.

## Lo que está a medias

- **Cal.diy sin enlazar**: ninguna actividad tiene `cal_event_type_id`, así que
  no hay reservas reales ni aforo. `alta_clases.py` es quien las da de alta.
- **Sesiones** sigue siendo una vista propia que depende de Cal.diy; el resumen
  semanal que se pidió vive ya en el Panel de control.
- **La web no publica los cambios de agenda**: `motivo_publico` se guarda pero
  nadie lo lee todavía.
- **Cierre mensual y anulación por el alumno**: diseñados, sin implementar. Ver
  el plan y el backlog.

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Esquema de NocoDB y datos de prueba | `scripts/provision-nocodb.py` |
| Acceso a NocoDB (única capa) | `scripts/backend/datos.py` |
| Filtro de la papelera | `scripts/nocolib.py` (`records`) |
| Proyección de clases y validación del lugar | `scripts/backend/agenda.py` |
| Servicios y actividades | `scripts/backend/handlers/actividades.py` |
| Lugares | `scripts/backend/handlers/lugares.py` |
| Papelera e impacto | `scripts/backend/handlers/papelera.py` |
| Panel de control | `scripts/backend/handlers/resumen.py` |
| Panel entero (HTML+CSS+JS en un fichero) | `sitio/admin/index.html` |
| Generación de la web pública | `scripts/build-web.py` |

## Lo que NO está en el repositorio

Al clonar en otra máquina falta:

- **`.env`** — credenciales de NocoDB, Cal.diy y DeepL. Sin esto no arranca nada.
- **`backups/`** — volcados de NocoDB. Llevan nombres, correos y teléfonos de
  alumnos, por eso están fuera de git.
- **`sitio/uploads/`** — fotos subidas desde el panel.
- **Los datos de NocoDB**, que viven en el volumen de `jmy-pg`, no en el repo.
