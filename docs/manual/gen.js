const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow,
  TableCell, WidthType, AlignmentType, LevelFormat, BorderStyle, ShadingType,
  TableOfContents, PageBreak,
} = require("docx");

const MAR = "20607E";
const TINTA = "26333D";
const ARENA = "EAE2D3";

const numbering = {
  config: [{
    reference: "vinetas",
    levels: [{
      level: 0, format: LevelFormat.BULLET, text: "\u2022",
      alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 460, hanging: 260 } } },
    }],
  }],
};

const p = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: 160 },
    children: [new TextRun({ text, size: 22, font: "Calibri", ...opts })],
    ...opts.para,
  });

const b = (bold, rest = "") =>
  new Paragraph({
    numbering: { reference: "vinetas", level: 0 },
    spacing: { after: 90 },
    children: [
      new TextRun({ text: bold, bold: true, size: 22, font: "Calibri" }),
      new TextRun({ text: rest, size: 22, font: "Calibri" }),
    ],
  });

const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 }, children: [new TextRun({ text: t, color: MAR })] });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 260, after: 140 }, children: [new TextRun({ text: t, color: TINTA })] });

const cell = (t, { bold = false, shade = false, w } = {}) =>
  new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: shade ? { type: ShadingType.CLEAR, fill: ARENA } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text: t, bold, size: 20, font: "Calibri" })] })],
  });

// ---------- Tabla mapa de herramientas ----------
const W = [1900, 3200, 1700, 2560]; // suma 9360
const mapaRows = [
  new TableRow({ tableHeader: true, children: [
    cell("Herramienta", { bold: true, shade: true, w: W[0] }),
    cell("Para qué sirve", { bold: true, shade: true, w: W[1] }),
    cell("Quién la usa", { bold: true, shade: true, w: W[2] }),
    cell("Dónde está", { bold: true, shade: true, w: W[3] }),
  ]}),
  ["La web", "Escaparate del negocio en 4 idiomas. Capta alumnos nuevos desde Google.", "Jose", "juliamoreno.yoga"],
  ["Ficha de Google", "Aparecer en el mapa cuando alguien busca \u201cyoga Nerja\u201d. Reseñas de alumnos.", "Julia y Jose", "App \u201cGoogle Maps\u201d / business.google.com"],
  ["WhatsApp Business", "Atender a alumnos e interesados. El canal principal de contacto.", "Julia", "App en el móvil"],
  ["Reservas", "Los alumnos reservan solos la clase de prueba y las privadas.", "Julia (agenda), Jose (ajustes)", "reservas.juliamoreno.yoga"],
  ["Fichero de alumnos", "Lista de alumnos, bonos vendidos y caducidades.", "Julia (apunta), Jose (mantiene)", "datos.juliamoreno.yoga"],
  ["Boletín de correo", "Correo mensual a alumnos e interesados. Sirve para llenar retiros.", "Julia (escribe), Jose (envía)", "correo.juliamoreno.yoga"],
  ["Estadísticas", "Saber cuánta gente visita la web y de dónde viene (carteles, Google\u2026).", "Jose", "stats.juliamoreno.yoga"],
  ["Automatizaciones", "Mensajes que se envían solos: recordatorios, avisos de bono, petición de reseña.", "Nadie (funciona solo)", "auto.juliamoreno.yoga"],
].map((r) => Array.isArray(r) ? new TableRow({ children: r.map((t, i) => cell(t, { w: W[i] })) }) : r);

const mapa = new Table({ columnWidths: W, width: { size: 9360, type: WidthType.DXA }, rows: mapaRows });

// ---------- Tabla rutinas ----------
const RW = [2200, 3580, 3580];
const rutinasRows = [
  new TableRow({ tableHeader: true, children: [
    cell("Frecuencia", { bold: true, shade: true, w: RW[0] }),
    cell("Julia", { bold: true, shade: true, w: RW[1] }),
    cell("Jose", { bold: true, shade: true, w: RW[2] }),
  ]}),
  ["Cada día (5 min)", "Responder WhatsApp. Apuntar asistencias y bonos vendidos en el fichero de alumnos.", "Nada."],
  ["Cada semana (30 min)", "Revisar la agenda de reservas de la semana. Contestar las reseñas nuevas de Google (basta un \u201cgracias\u201d personalizado).", "Una publicación en la ficha de Google y otra en Instagram (foto de clase + texto breve). Mirar las estadísticas: qué trae visitas."],
  ["Cada mes (1 hora, juntos)", "Decidir el tema del boletín del mes y escribir el texto (10-15 líneas bastan).", "Maquetar y enviar el boletín. Actualizar horarios o precios en la web si han cambiado. Repasar bonos caducados en el fichero."],
  ["Cada trimestre", "Revisar precios frente a la competencia. Planificar el siguiente retiro o taller.", "Copia de seguridad comprobada con el informático. Refrescar fotos de la web y de la ficha."],
].map((r) => Array.isArray(r) ? new TableRow({ children: r.map((t, i) => cell(t, { w: RW[i] })) }) : r);

const rutinas = new Table({ columnWidths: RW, width: { size: 9360, type: WidthType.DXA }, rows: rutinasRows });

// ---------- Documento ----------
const doc = new Document({
  numbering,
  styles: {
    default: {
      heading1: { run: { font: "Calibri", size: 32, bold: true } },
      heading2: { run: { font: "Calibri", size: 26, bold: true } },
      document: { run: { font: "Calibri", size: 22 } },
    },
  },
  sections: [{
    properties: {},
    children: [
      new Paragraph({ spacing: { before: 2400, after: 200 }, alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Julia Moreno · Yoga", size: 64, bold: true, color: MAR, font: "Calibri" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
        children: [new TextRun({ text: "Manual de las herramientas del negocio", size: 32, color: TINTA, font: "Calibri" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 3000 },
        children: [new TextRun({ text: "Para Julia y Jose \u00b7 julio de 2026", size: 22, color: "5C6A75", font: "Calibri" })] }),
      new Paragraph({ children: [new PageBreak()] }),

      h1("1. El mapa: qué es cada cosa"),
      p("El negocio se apoya en ocho piezas. Ninguna requiere conocimientos técnicos: todas se usan desde el navegador o el móvil, con usuario y contraseña. La instalación y las averías son cosa del informático; este manual explica solo el uso del día a día."),
      mapa,
      p(""),
      p("Regla de oro: no hace falta usarlo todo desde el primer día. El orden de adopción recomendado es: ficha de Google \u2192 WhatsApp Business \u2192 reservas \u2192 fichero de alumnos \u2192 boletín. Cada herramienta se incorpora cuando la anterior ya es rutina.", { italics: true }),

      h1("2. La web (juliamoreno.yoga)"),
      p("Es el escaparate: quien busca \u201cyoga Nerja\u201d en Google (en español, inglés, francés o alemán) debe acabar aquí, y de aquí al WhatsApp de Julia. La web ya está hecha; el trabajo es mantenerla viva."),
      h2("Responsable: Jose"),
      b("Cambios de horarios y precios: ", "avisar al informático o editarlos directamente si se le ha dado acceso. Nunca dejar en la web un horario que ya no es real: es la primera causa de mala impresión."),
      b("Fotos: ", "renovar las fotos cada temporada. Fotos reales de clases (con permiso de los alumnos) convierten mucho más que imágenes de banco."),
      b("Qué no tocar: ", "los textos de posicionamiento (títulos, descripciones) están escritos para Google; cualquier cambio de fondo, consultarlo antes."),
      h2("Lo que Julia debe saber"),
      b("Su credencial universitaria es el mensaje central de la web. ", "En conversaciones, carteles y redes conviene repetirlo igual: \u201cgraduada en Ciencias del Deporte, experta en Hatha yoga\u201d."),

      h1("3. La ficha de Google (la pieza más importante)"),
      p("Cuando alguien busca \u201cyoga Nerja\u201d, Google muestra primero un mapa con tres negocios. Estar ahí vale más que cualquier publicidad, y se consigue con reseñas frecuentes y una ficha viva."),
      h2("Julia: pedir reseñas (la tarea con más impacto de todo el manual)"),
      b("A quién: ", "a cada alumno contento, especialmente tras su primera clase. Los alumnos de todo este año pasado también cuentan: una campaña inicial pidiéndoselo a todos por WhatsApp coloca la ficha en cabeza en pocas semanas."),
      b("Cómo: ", "mensaje de WhatsApp con el enlace directo a la reseña (el informático lo prepara acortado). Modelo: \u201c\u00a1Gracias por venir hoy! Si te ha gustado la clase, me ayudarías muchísimo dejando una reseña aquí (1 minuto): [enlace]\u201d."),
      b("Responder siempre: ", "a cada reseña, dos líneas personalizadas. Google lo premia y los futuros alumnos lo leen."),
      h2("Jose: mantener la ficha viva"),
      b("Una publicación semanal: ", "foto de clase, horario destacado, taller próximo. Cinco minutos."),
      b("Fotos nuevas cada mes ", "y datos siempre al día: horarios, teléfono, zona de servicio (Nerja, Maro y, si se confirma, Almuñécar)."),

      h1("4. WhatsApp Business (Julia)"),
      p("Es WhatsApp normal con herramientas de negocio gratuitas. Se migra el número actual sin perder nada."),
      b("Mensaje de bienvenida automático: ", "se configura una vez. Modelo: \u201c\u00a1Hola! Soy Julia. Cuéntame qué buscas (clase de prueba, horarios, privadas) y te respondo hoy mismo\u201d."),
      b("Respuestas rápidas: ", "textos guardados que se insertan escribiendo /. Conviene tener: /horarios, /precios, /donde (ubicación), /resena (petición de reseña), /prueba (cómo reservar la clase de prueba)."),
      b("Etiquetas: ", "marcar cada conversación como \u201cInteresado\u201d, \u201cAlumno\u201d, \u201cRetiro\u201d. Es la forma más simple de no perder a nadie."),
      b("Catálogo: ", "publicar los bonos y precios en el perfil, así muchos ni preguntan."),

      h1("5. Reservas (reservas.juliamoreno.yoga)"),
      p("Los interesados eligen hueco para la clase de prueba o una privada y reciben confirmación y recordatorio automáticos. Menos mensajes cruzados, menos plantones."),
      h2("Julia"),
      b("Mantener la disponibilidad al día: ", "si un jueves no puede, bloquearlo en la agenda. La herramienta se sincroniza con su calendario del móvil."),
      b("Revisar la agenda cada domingo: ", "las reservas de la semana entrante aparecen en su calendario."),
      h2("Jose"),
      b("Ajustar los \u201ctipos de cita\u201d ", "(clase de prueba 60 min, privada 75 min, valoración inicial) cuando cambien duración o condiciones."),

      h1("6. El fichero de alumnos (datos.juliamoreno.yoga)"),
      p("Una hoja de cálculo mejorada en internet con tres pestañas: Alumnos, Bonos y Asistencias. Sustituye a la libreta y permite que los avisos automáticos funcionen."),
      h2("Julia: dos apuntes por día como máximo"),
      b("Alumno nuevo: ", "nombre, teléfono e idioma. Treinta segundos."),
      b("Venta de bono: ", "alumno, tipo de bono (4 u 8 clases), fecha. La caducidad se calcula sola."),
      h2("Jose"),
      b("Revisar una vez al mes ", "bonos caducados y datos incompletos. No cambiar la estructura de las tablas sin consultar: los avisos automáticos dependen de ella."),

      h1("7. El boletín de correo (correo.juliamoreno.yoga)"),
      p("Un correo al mes a alumnos e interesados. Es el canal que llena los retiros y los talleres: la lista de correo es propia y nadie cobra comisión por usarla."),
      b("Julia escribe: ", "10-15 líneas: novedad del mes, un consejo de práctica, y el anuncio del próximo taller o retiro si lo hay. Sin pretensiones literarias: cercano y breve funciona mejor."),
      b("Jose envía: ", "pega el texto en la plantilla, elige la lista y programa el envío. Primera semana del mes, siempre igual."),
      b("Cómo crece la lista: ", "cada alumno nuevo se pregunta si quiere recibirlo (y se apunta en el fichero); en la web hay un formulario de alta. Nunca añadir a nadie sin su permiso."),

      h1("8. Estadísticas (stats.juliamoreno.yoga)"),
      p("Responsable: Jose. Una mirada semanal de cinco minutos responde a tres preguntas: cuánta gente visitó la web, desde dónde llegó (Google, Instagram, el QR de los carteles) y qué páginas miró. Cada cartel lleva un QR distinto, así que se sabe qué zonas de pegada funcionan y cuáles no. Con eso se decide dónde reponer carteles y qué contenido publicar más."),

      h1("9. Las automatizaciones (funcionan solas)"),
      p("Hay mensajes que el sistema envía sin que nadie haga nada, a partir de lo apuntado en el fichero de alumnos y las reservas:"),
      b("Recordatorio de clase ", "al alumno con reserva, el día antes."),
      b("Aviso de bono a punto de caducar, ", "tres días antes, con invitación a renovarlo."),
      b("Petición de reseña ", "unas horas después de la primera clase de un alumno nuevo."),
      p("Si alguno de estos mensajes deja de llegar o llega mal, no tocar nada: avisar al informático."),

      h1("10. Rutinas de trabajo"),
      p("Todo el sistema se sostiene con esto:"),
      rutinas,

      h1("11. Contraseñas y seguridad"),
      b("Un gestor de contraseñas compartido ", "(el informático lo instala, por ejemplo Bitwarden): una contraseña distinta por herramienta y las dos personas con acceso. Nunca en una libreta ni repetidas."),
      b("Verificación en dos pasos ", "activada al menos en Google y en el correo."),
      b("Nunca compartir contraseñas por WhatsApp ", "ni con nadie que las pida por teléfono o correo, aunque diga ser de Google: Google no llama."),

      h1("12. Cuando algo falla"),
      p("Cualquier avería (la web no carga, un aviso no llegó, no se puede entrar en una herramienta) se comunica al informático con tres datos: qué se intentaba hacer, qué pantalla o mensaje apareció (mejor con captura) y a qué hora ocurrió. Con eso se resuelve casi todo a la primera."),
      p("Y la regla final: si una herramienta no se está usando, es mejor decirlo que arrastrarla. Se apaga y no pasa nada. Este sistema está al servicio de las clases, no al revés.", { italics: true }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("/home/claude/manual/manual-herramientas-yogaconjulia.docx", buf);
  console.log("OK", buf.length);
});
