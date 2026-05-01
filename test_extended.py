"""
100 mensajes realistas con empleados ficticios por departamento y personalidad.
expected_tipo refleja la clasificación correcta — no siempre la que devolvió el modelo.
Casos NO_REPORTE marcados explícitamente para entrenar la frontera gossip vs operacional.
"""

LAURA    = {"nombre": "Laura",   "departamento": "RECEPCION",    "idioma": "es"}
ELENA    = {"nombre": "Elena",   "departamento": "RECEPCION",    "idioma": "es"}
PABLO    = {"nombre": "Pablo",   "departamento": "RECEPCION",    "idioma": "es"}
LUCIA    = {"nombre": "Lucia",   "departamento": "HOUSEKEEPING", "idioma": "es"}
PEDRO    = {"nombre": "Pedro",   "departamento": "HOUSEKEEPING", "idioma": "es"}
BEATRIZ  = {"nombre": "Beatriz", "departamento": "HOUSEKEEPING", "idioma": "es"}
ROSA     = {"nombre": "Rosa",    "departamento": "OTRO",         "idioma": "es"}
DAVID    = {"nombre": "David",   "departamento": "OTRO",         "idioma": "es"}
CARMEN   = {"nombre": "Carmen",  "departamento": "OTRO",         "idioma": "es"}
MIGUEL   = {"nombre": "Miguel",  "departamento": "RESTAURANTE",  "idioma": "es"}
CARLOS   = {"nombre": "Carlos",  "departamento": "RESTAURANTE",  "idioma": "es"}
ANAR     = {"nombre": "AnaR",    "departamento": "RESTAURANTE",  "idioma": "es"}
FERNANDO = {"nombre": "Fernando","departamento": "MANTENIMIENTO","idioma": "es"}
ANDREI   = {"nombre": "Andrei",  "departamento": "MANTENIMIENTO","idioma": "es"}
ISABEL   = {"nombre": "Isabel",  "departamento": "OTRO",         "idioma": "es"}
RAUL     = {"nombre": "Raul",    "departamento": "OTRO",         "idioma": "es"}
JAVIER   = {"nombre": "Javier",  "departamento": "OTRO",         "idioma": "es"}
SOFIA    = {"nombre": "Sofia",   "departamento": "OTRO",         "idioma": "es"}
MARCOS   = {"nombre": "Marcos",  "departamento": "OTRO",         "idioma": "es"}

TEST_EXTENDED = [
    # 1
    {"id": "EXT-001", "employee": LAURA,
     "message": "Habitación 204. Cliente Sr. Müller pidió almohada hipoalergénica adicional a las 21:14. Confirmado que la original tenía etiqueta de plumas. Se cambió correctamente. Cliente alemán, extremadamente puntual.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia + alergia + contexto cultural. Obsesivo con detalle."},

    # 2
    {"id": "EXT-002", "employee": PEDRO,
     "message": "La pareja del jacuzzi privado… los que parecían recién casados. Dejaron pétalos por todos lados. Muy amables.",
     "expected_tipo": "GUEST_INTEL", "notes": "Contexto sobre huéspedes. Sin habitación — Pedro distraído."},

    # 3
    {"id": "EXT-003", "employee": CARMEN,
     "message": "Ojo con la rubia del yoga, anda coqueteando fuerte con el instructor de paddle. Creo que el marido ni se enteró.",
     "expected_tipo": "NO_REPORTE", "notes": "Gossip puro, sin valor operacional para el hotel."},

    # 4
    {"id": "EXT-004", "employee": MIGUEL,
     "message": "Mesa 12, huésped habitación 318. Alergia confirmada a nueces y pistacho. Se informó cocina y jefe de sala. Cliente pidió doble verificación.",
     "expected_tipo": "GUEST_INTEL", "notes": "Alergia crítica. Obsesivo: incluye mesa, hab, doble verificación."},

    # 5
    {"id": "EXT-005", "employee": ANDREI,
     "message": "Hay una luz que parpadea cerca de donde está el cuadro ese azul grande. El huésped dijo que no pudo dormir bien.",
     "expected_tipo": "INCIDENCIA", "notes": "Falla técnica. Distraído: sin ubicación exacta."},

    # 6
    {"id": "EXT-006", "employee": SOFIA,
     "message": "El señor musculoso que vino para competición amateur de culturismo está tomando vodka escondido en botella térmica.",
     "expected_tipo": "GUEST_INTEL", "notes": "RIESGO — consumo de alcohol propio en instalaciones del hotel."},

    # 7
    {"id": "EXT-007", "employee": LAURA,
     "message": "Habitación 110. Huésped solicita wake-up call exactamente 05:45, no 05:50. Vuelo hacia Zúrich.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia precisa. Típico de obsesivo con contexto viaje."},

    # 8
    {"id": "EXT-008", "employee": PEDRO,
     "message": "Encontré magnesio en polvo y unos mosquetones. Creo que el huésped hace escalada.",
     "expected_tipo": "GUEST_INTEL", "notes": "Contexto sobre perfil del huésped. Sin habitación."},

    # 9
    {"id": "EXT-009", "employee": ISABEL,
     "message": "La señora inglesa dijo que 'necesitaba vacaciones de sus hijos'. Lleva tres días ignorando llamadas del marido.",
     "expected_tipo": "NO_REPORTE", "notes": "Gossip sobre vida personal. Sin valor operacional."},

    # 10
    {"id": "EXT-010", "employee": ROSA,
     "message": "Cliente habitación 412 informó embarazo de 4 meses. Solo tratamientos prenatales autorizados. Registrado correctamente.",
     "expected_tipo": "GUEST_INTEL", "notes": "Info médica crítica. Obsesivo con protocolo correcto."},

    # 11
    {"id": "EXT-011", "employee": CARLOS,
     "message": "El señor de barba pidió carne muy poco hecha y después dijo que estaba demasiado cocida.",
     "expected_tipo": "GUEST_INTEL", "notes": "Patrón de comportamiento de huésped difícil. Sin habitación."},

    # 12
    {"id": "EXT-012", "employee": ELENA,
     "message": "La chica argentina del 221 parece influencer. Se pasó una hora sacando fotos en escalera principal.",
     "expected_tipo": "GUEST_INTEL", "notes": "VIP potencial. Chismosa pero con valor operacional."},

    # 13
    {"id": "EXT-013", "employee": LUCIA,
     "message": "Habitación 305. Se detectó fuga mínima en bidet. Reportado a mantenimiento 14:32.",
     "expected_tipo": "INCIDENCIA", "notes": "Falla técnica con hora exacta. Obsesiva."},

    # 14
    {"id": "EXT-014", "employee": MARCOS,
     "message": "Un huésped dejó un reloj caro. Creo que era suizo o algo así.",
     "expected_tipo": "GUEST_INTEL", "notes": "Objeto olvidado. Distraído: sin habitación ni descripción exacta."},

    # 15
    {"id": "EXT-015", "employee": SOFIA,
     "message": "Los del bungalow del fondo están peleando fuerte todas las noches pero después desayunan abrazados.",
     "expected_tipo": "OBSERVACION", "notes": "Patrón nocturno repetido. OBSERVACION es válido; GUEST_INTEL también (RIESGO). Aceptamos OBSERVACION."},

    # 16
    {"id": "EXT-016", "employee": LAURA,
     "message": "Habitación 509. Cliente solicitó taxi Mercedes exclusivamente. Rechazó vehículo estándar.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia de transporte. Obsesiva con detalle."},

    # 17
    {"id": "EXT-017", "employee": DAVID,
     "message": "El cliente tatuado quería masaje fuerte. Creo que era deportista profesional o entrenador.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia de tratamiento. Sin habitación."},

    # 18
    {"id": "EXT-018", "employee": ANAR,
     "message": "El chef dice que la señora francesa manda devolver TODO solo para llamar la atención.",
     "expected_tipo": "GUEST_INTEL", "notes": "Comportamiento problemático repetido. Relevante para cocina y sala."},

    # 19
    {"id": "EXT-019", "employee": LUCIA,
     "message": "Habitación 118. Cliente dejó laptop abierta al salir. Puerta asegurada nuevamente a las 10:07.",
     "expected_tipo": "GUEST_INTEL", "notes": "Seguridad del huésped gestionada. Obsesiva con hora."},

    # 20
    {"id": "EXT-020", "employee": MARCOS,
     "message": "Niño perdió flotador rojo cerca de las hamacas.",
     "expected_tipo": "INCIDENCIA", "notes": "Objeto perdido con acción inmediata. Sin habitación."},

    # 21
    {"id": "EXT-021", "employee": ISABEL,
     "message": "El huésped italiano vino supuestamente 'solo', pero ayer apareció otra mujer distinta.",
     "expected_tipo": "NO_REPORTE", "notes": "Gossip sobre vida personal. Sin implicación operacional."},

    # 22
    {"id": "EXT-022", "employee": LAURA,
     "message": "Habitación 402. Cliente intolerante a lactosa confirmado. Nota agregada a perfil PMS.",
     "expected_tipo": "GUEST_INTEL", "notes": "Restricción alimentaria. Obsesiva con confirmación en PMS."},

    # 23
    {"id": "EXT-023", "employee": ANDREI,
     "message": "Aire acondicionado raro en habitación con vista mar… hace sonido como motor viejo.",
     "expected_tipo": "INCIDENCIA", "notes": "Falla técnica. Distraído: sin número de habitación."},

    # 24
    {"id": "EXT-024", "employee": ANAR,
     "message": "El culturista de antes pesa la comida con balanza portátil. Muy intenso.",
     "expected_tipo": "NO_REPORTE", "notes": "Curiosidad sin valor operacional. El hotel no necesita actuar."},

    # 25
    {"id": "EXT-025", "employee": ROSA,
     "message": "Cliente habitación 210 pidió evitar aceites con fragancia cítrica. Posible sensibilidad dérmica.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia de tratamiento con alerta médica. Obsesiva."},

    # 26
    {"id": "EXT-026", "employee": PEDRO,
     "message": "La señora del sombrero grande dejó muchísimos libros de astrología por todos lados.",
     "expected_tipo": "INCIDENCIA", "notes": "Habitación con objetos por todos lados → housekeeping tiene tarea. INCIDENCIA (orden/limpieza)."},

    # 27
    {"id": "EXT-027", "employee": ELENA,
     "message": "Creo que el señor del 333 le mintió a la esposa. Dijo viaje de negocios pero anda todo el día en spa.",
     "expected_tipo": "NO_REPORTE", "notes": "Gossip sobre vida privada. Sin valor para el hotel."},

    # 28
    {"id": "EXT-028", "employee": JAVIER,
     "message": "Cliente habitación 615 consumió 4 negronis entre 19:10 y 21:02. Firmó correctamente.",
     "expected_tipo": "GUEST_INTEL", "notes": "Registro de consumo. Obsesivo con horarios exactos."},

    # 29
    {"id": "EXT-029", "employee": CARLOS,
     "message": "Mesa grande celebrando algo… cumpleaños o divorcio, no entendí bien.",
     "expected_tipo": "GUEST_INTEL", "notes": "Ocasión especial vaga. Distraído: sin habitación ni confirmación."},

    # 30
    {"id": "EXT-030", "employee": ISABEL,
     "message": "La huésped rusa anda preguntando mucho por quiénes tienen villas privadas.",
     "expected_tipo": "GUEST_INTEL", "notes": "VIP/RIESGO — interés en datos de otros huéspedes es señal a registrar."},

    # 31
    {"id": "EXT-031", "employee": LUCIA,
     "message": "Habitación 440. Encontradas manchas de maquillaje en 3 toallas grandes. Registrado para lavandería especial.",
     "expected_tipo": "INCIDENCIA", "notes": "Ropa de cama dañada. Obsesiva con inventario exacto."},

    # 32
    {"id": "EXT-032", "employee": DAVID,
     "message": "Uno pidió masaje pero después quería hablar de criptomonedas todo el tiempo.",
     "expected_tipo": "NO_REPORTE", "notes": "Anécdota sin valor operacional."},

    # 33
    {"id": "EXT-033", "employee": ELENA,
     "message": "La pareja joven parece luna de miel. No salen casi de la habitación.",
     "expected_tipo": "GUEST_INTEL", "notes": "OCASION — luna de miel es dato accionable para el hotel."},

    # 34
    {"id": "EXT-034", "employee": FERNANDO,
     "message": "Revisada presión de agua habitación 227. Valores normales tras reclamo huésped.",
     "expected_tipo": "OBSERVACION", "notes": "Verificación completada, sin acción pendiente. Registro operativo."},

    # 35
    {"id": "EXT-035", "employee": CARLOS,
     "message": "Cliente pidió vino italiano específico… algo terminado en -ini.",
     "expected_tipo": "GUEST_INTEL", "notes": "Solicitud específica sin resolver. Sin habitación."},

    # 36
    {"id": "EXT-036", "employee": MARCOS,
     "message": "El profesor de buceo dice que el huésped alemán se cree experto pero casi se ahoga ayer.",
     "expected_tipo": "GUEST_INTEL", "notes": "RIESGO — seguridad acuática de huésped específico."},

    # 37
    {"id": "EXT-037", "employee": LUCIA,
     "message": "Habitación 120. Cliente solicitó cambio exacto de orientación de cama auxiliar. Ejecutado.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia de alojamiento muy específica. Obsesiva."},

    # 38
    {"id": "EXT-038", "employee": PABLO,
     "message": "Uno perdió pasaporte creo. Estaba muy nervioso.",
     "expected_tipo": "GUEST_INTEL", "notes": "Emergencia documental. Distraído: sin nombre ni habitación."},

    # 39
    {"id": "EXT-039", "employee": CARMEN,
     "message": "La señora del kimono blanco dejó propina enorme al terapeuta joven. Raro.",
     "expected_tipo": "NO_REPORTE", "notes": "Observación curiosa sin valor operacional directo."},

    # 40
    {"id": "EXT-040", "employee": MIGUEL,
     "message": "Mesa 7. Cliente celíaco confirmado. Se usaron utensilios separados.",
     "expected_tipo": "GUEST_INTEL", "notes": "Restricción alimentaria. Protocolo seguido."},

    # 41
    {"id": "EXT-041", "employee": RAUL,
     "message": "Alguien quería alquilar bicicleta eléctrica mañana temprano.",
     "expected_tipo": "GUEST_INTEL", "notes": "Solicitud pendiente. Distraído: sin nombre ni habitación."},

    # 42
    {"id": "EXT-042", "employee": JAVIER,
     "message": "Dos huéspedes discutían sobre herencia familiar tomando whisky caro.",
     "expected_tipo": "NO_REPORTE", "notes": "Conversación privada de huéspedes. Sin acción posible."},

    # 43
    {"id": "EXT-043", "employee": LUCIA,
     "message": "Habitación 502. Minibar consumido parcialmente: 2 aguas, 1 prosecco, 3 almendras saladas.",
     "expected_tipo": "INCIDENCIA", "notes": "Minibar consumido → reponer y facturar. Acción operativa inmediata."},

    # 44
    {"id": "EXT-044", "employee": PABLO,
     "message": "Cliente fanático de aves preguntó por rutas para ver halcones.",
     "expected_tipo": "GUEST_INTEL", "notes": "Interés del huésped. Sin habitación."},

    # 45
    {"id": "EXT-045", "employee": ANAR,
     "message": "El chef cree que el crítico gastronómico hospedado acá usa nombre falso.",
     "expected_tipo": "GUEST_INTEL", "notes": "VIP relevante — crítico gastronómico tiene impacto directo en restaurante."},

    # 46
    {"id": "EXT-046", "employee": ROSA,
     "message": "Cliente habitación 145 indicó lesión antigua en hombro izquierdo. Presión moderada únicamente.",
     "expected_tipo": "GUEST_INTEL", "notes": "Condición física que afecta el tratamiento."},

    # 47
    {"id": "EXT-047", "employee": ANDREI,
     "message": "Hay olor raro en pasillo segundo piso, tipo humedad o perfume fuerte.",
     "expected_tipo": "INCIDENCIA", "notes": "Posible problema de humedad en zona común. Sin ubicación exacta."},

    # 48
    {"id": "EXT-048", "employee": ISABEL,
     "message": "El huésped francés vino para pedir matrimonio. Tiene escondido el anillo en recepción.",
     "expected_tipo": "GUEST_INTEL", "notes": "OCASION — muy accionable. Coordinar decoración, champán, etc."},

    # 49
    {"id": "EXT-049", "employee": LUCIA,
     "message": "Habitación 608. Cliente pidió exactamente 6 perchas adicionales. Entregadas 16:41.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia completada. Obsesiva con hora y cantidad exacta."},

    # 50
    {"id": "EXT-050", "employee": MARCOS,
     "message": "La niña del flotador unicornio lloraba porque perdió unas gafas rosas.",
     "expected_tipo": "GUEST_INTEL", "notes": "Objeto perdido de huésped menor. Sin habitación."},

    # 51
    {"id": "EXT-051", "employee": JAVIER,
     "message": "El DJ que vino al evento terminó besándose con una huésped casada.",
     "expected_tipo": "NO_REPORTE", "notes": "Gossip sin valor operacional para el hotel."},

    # 52
    {"id": "EXT-052", "employee": LAURA,
     "message": "Habitación 230. Cliente requiere desayuno vegano sin soja. Nota enviada a cocina.",
     "expected_tipo": "GUEST_INTEL", "notes": "Restricción alimentaria enviada a cocina. Obsesiva."},

    # 53
    {"id": "EXT-053", "employee": CARLOS,
     "message": "Señor mayor pidió sopa aunque hacía muchísimo calor afuera.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia específica de huésped. Sin habitación."},

    # 54
    {"id": "EXT-054", "employee": BEATRIZ,
     "message": "Creo que los del 410 filman videos para internet… tenían luces raras y cámaras.",
     "expected_tipo": "GUEST_INTEL", "notes": "RIESGO — grabación en habitación. Posible violación de política del hotel."},

    # 55
    {"id": "EXT-055", "employee": ROSA,
     "message": "Cliente habitación 319 indicó presión arterial alta. Evitar sauna prolongado.",
     "expected_tipo": "GUEST_INTEL", "notes": "Condición médica relevante para spa. Obsesiva."},

    # 56
    {"id": "EXT-056", "employee": ANDREI,
     "message": "Televisor de una habitación no conecta Netflix.",
     "expected_tipo": "INCIDENCIA", "notes": "Falla técnica. Distraído: sin número de habitación."},

    # 57
    {"id": "EXT-057", "employee": ISABEL,
     "message": "La influencer fitness anda exigiendo agua alcalina importada.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia exigente. Sin habitación."},

    # 58
    {"id": "EXT-058", "employee": LAURA,
     "message": "Habitación 150. Late checkout aprobado hasta 14:00. Cargo adicional aplicado.",
     "expected_tipo": "GUEST_INTEL", "notes": "Servicio adicional registrado. Obsesiva."},

    # 59
    {"id": "EXT-059", "employee": CARLOS,
     "message": "Cliente dejó sombrero elegante colgado en silla.",
     "expected_tipo": "INCIDENCIA", "notes": "Objeto olvidado con acción pendiente. Sin habitación."},

    # 60
    {"id": "EXT-060", "employee": SOFIA,
     "message": "El entrenador de triatlón se emborrachó y terminó llorando por su ex.",
     "expected_tipo": "GUEST_INTEL", "notes": "RIESGO — huésped en estado de embriaguez requiere atención."},

    # 61
    {"id": "EXT-061", "employee": LUCIA,
     "message": "Habitación 288. Cliente solicitó limpieza únicamente entre 11:00 y 11:30.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia de horario. Obsesiva con ventana exacta."},

    # 62
    {"id": "EXT-062", "employee": DAVID,
     "message": "Había uno que meditaba raro en silencio total antes del masaje.",
     "expected_tipo": "NO_REPORTE", "notes": "Anécdota curiosa sin impacto operacional."},

    # 63
    {"id": "EXT-063", "employee": ELENA,
     "message": "El huésped famoso de televisión pidió entrar por puerta trasera.",
     "expected_tipo": "GUEST_INTEL", "notes": "VIP — solicitud de discreción. Accionable para recepción."},

    # 64
    {"id": "EXT-064", "employee": MIGUEL,
     "message": "Mesa 14. Cliente alérgico a mariscos. Riesgo de contaminación cruzada informado.",
     "expected_tipo": "GUEST_INTEL", "notes": "Alergia crítica. Protocolo de cocina activado."},

    # 65
    {"id": "EXT-065", "employee": ANDREI,
     "message": "Ducha pierde agua hacia el pasillo en habitación… creo que 3 algo.",
     "expected_tipo": "INCIDENCIA", "notes": "Fuga activa. Distraído: número de habitación incompleto."},

    # 66
    {"id": "EXT-066", "employee": ISABEL,
     "message": "La señora elegante del penthouse odia a otra huésped y pide no coincidir en spa.",
     "expected_tipo": "GUEST_INTEL", "notes": "RIESGO — conflicto entre huéspedes. Requiere coordinación de spa."},

    # 67
    {"id": "EXT-067", "employee": LUCIA,
     "message": "Habitación 377. Encontrado cargador Apple bajo cama durante inspección post-checkout.",
     "expected_tipo": "INCIDENCIA", "notes": "Objeto olvidado post-checkout → hay que contactar al huésped. Acción inmediata."},

    # 68
    {"id": "EXT-068", "employee": MARCOS,
     "message": "Huésped preguntó si se podía entrenar apnea en piscina chica.",
     "expected_tipo": "GUEST_INTEL", "notes": "Solicitud con implicación de seguridad. Sin habitación."},

    # 69
    {"id": "EXT-069", "employee": JAVIER,
     "message": "El empresario español cerró negocio enorme anoche acá mismo tomando coñac.",
     "expected_tipo": "NO_REPORTE", "notes": "Anécdota sin valor operacional para el hotel."},

    # 70
    {"id": "EXT-070", "employee": ROSA,
     "message": "Cliente habitación 555 pidió evitar conversación durante tratamiento. Preferencia registrada.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia de comunicación. Obsesiva."},

    # 71
    {"id": "EXT-071", "employee": CARLOS,
     "message": "Niño tiró jugo encima de señora elegante.",
     "expected_tipo": "INCIDENCIA", "notes": "Incidente con limpieza urgente. Sin habitación."},

    # 72
    {"id": "EXT-072", "employee": ELENA,
     "message": "Creo que el huésped canadiense escribe novelas policiales. Siempre observa a todos.",
     "expected_tipo": "NO_REPORTE", "notes": "Especulación curiosa sin acción posible."},

    # 73
    {"id": "EXT-073", "employee": LUCIA,
     "message": "Habitación 260. Temperatura ajustada manualmente a 19°C según preferencia huésped.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia de temperatura registrada. Obsesiva."},

    # 74
    {"id": "EXT-074", "employee": ANDREI,
     "message": "Escuché ruido metálico cerca ascensor servicio.",
     "expected_tipo": "INCIDENCIA", "notes": "Posible falla mecánica en ascensor. Urgente verificar."},

    # 75
    {"id": "EXT-075", "employee": ISABEL,
     "message": "El huésped japonés vino para competencia internacional de ajedrez rápido.",
     "expected_tipo": "GUEST_INTEL", "notes": "Contexto de visita. Posible coordinación de servicios."},

    # 76
    {"id": "EXT-076", "employee": MIGUEL,
     "message": "Mesa 3. Cliente solicitó agua exactamente sin hielo y con rodaja fina de limón.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencia muy específica. Obsesivo con detalle."},

    # 77
    {"id": "EXT-077", "employee": DAVID,
     "message": "La señora que corre maratones tenía piernas súper cargadas.",
     "expected_tipo": "GUEST_INTEL", "notes": "Info relevante para adaptar tratamiento de spa."},

    # 78
    {"id": "EXT-078", "employee": JAVIER,
     "message": "Dos huéspedes intentaron colarse después del cierre diciendo que conocían al dueño.",
     "expected_tipo": "INCIDENCIA", "notes": "Intento de acceso no autorizado. RIESGO de seguridad."},

    # 79
    {"id": "EXT-079", "employee": LAURA,
     "message": "Habitación 199. Cliente solicitó almohada firme adicional y manta de algodón orgánico.",
     "expected_tipo": "GUEST_INTEL", "notes": "Preferencias de cama específicas. Obsesiva."},

    # 80
    {"id": "EXT-080", "employee": PEDRO,
     "message": "Habitación llena de mapas y botas embarradas. Excursionistas seguro.",
     "expected_tipo": "GUEST_INTEL", "notes": "Perfil de huésped. Sin habitación. Posible limpieza extra."},

    # 81
    {"id": "EXT-081", "employee": ANAR,
     "message": "La pareja del desayuno no se hablaba pero después se agarraban la mano debajo de mesa.",
     "expected_tipo": "NO_REPORTE", "notes": "Observación personal sin valor operacional."},

    # 82
    {"id": "EXT-082", "employee": MARCOS,
     "message": "Cliente habitación 601 reportó temperatura piscina '2 grados inferior a lo ideal'. Medición realizada.",
     "expected_tipo": "INCIDENCIA", "notes": "Reclamo con medición. Puede requerir ajuste."},

    # 83
    {"id": "EXT-083", "employee": RAUL,
     "message": "Uno quería clases privadas de guitarra flamenca.",
     "expected_tipo": "GUEST_INTEL", "notes": "Solicitud de servicio adicional. Sin datos del huésped."},

    # 84
    {"id": "EXT-084", "employee": CARMEN,
     "message": "El huésped musculoso toma selfies sin camiseta en cada espejo del spa.",
     "expected_tipo": "NO_REPORTE", "notes": "Comportamiento molesto pero sin impacto operacional directo."},

    # 85
    {"id": "EXT-085", "employee": FERNANDO,
     "message": "Revisado extractor baño habitación 347. Funcionamiento correcto pese a reclamo.",
     "expected_tipo": "OBSERVACION", "notes": "Verificación técnica sin incidencia. Registro operativo."},

    # 86
    {"id": "EXT-086", "employee": PABLO,
     "message": "Cliente preguntó por iglesia antigua para misa temprano.",
     "expected_tipo": "GUEST_INTEL", "notes": "Solicitud de información local. Sin habitación."},

    # 87
    {"id": "EXT-087", "employee": ANAR,
     "message": "El chef y la sommelier están peleados otra vez. Se nota muchísimo en servicio.",
     "expected_tipo": "OBSERVACION", "notes": "Problema interno que afecta calidad del servicio. No es GUEST_INTEL."},

    # 88
    {"id": "EXT-088", "employee": LUCIA,
     "message": "Habitación 480. Cliente dejó joyería visible. Caja fuerte recomendada verbalmente.",
     "expected_tipo": "GUEST_INTEL", "notes": "Seguridad del huésped gestionada proactivamente."},

    # 89
    {"id": "EXT-089", "employee": MARCOS,
     "message": "Un huésped tocó piano y cantó tangos hasta tarde.",
     "expected_tipo": "GUEST_INTEL", "notes": "Comportamiento en zona común. Potencial molestia para otros."},

    # 90
    {"id": "EXT-090", "employee": ISABEL,
     "message": "La chica del retiro espiritual fuma escondida detrás del parking.",
     "expected_tipo": "GUEST_INTEL", "notes": "RIESGO — fumando en zona no autorizada. Política del hotel."},

    # 91
    {"id": "EXT-091", "employee": ROSA,
     "message": "Cliente habitación 214 canceló tratamiento 13 minutos antes. Cargo aplicado según política.",
     "expected_tipo": "GUEST_INTEL", "notes": "Registro de cargo y comportamiento. Obsesiva con minutos."},

    # 92
    {"id": "EXT-092", "employee": CARLOS,
     "message": "Había un perro pequeño debajo de una mesa aunque creo que no se permiten.",
     "expected_tipo": "INCIDENCIA", "notes": "Infracción de política. Requiere intervención."},

    # 93
    {"id": "EXT-093", "employee": ELENA,
     "message": "El huésped del ático pidió flores para 'una visita especial' a medianoche.",
     "expected_tipo": "GUEST_INTEL", "notes": "OCASION — solicitud de decoración. Accionable."},

    # 94
    {"id": "EXT-094", "employee": LUCIA,
     "message": "Habitación 390. Cliente requiere únicamente productos de limpieza sin perfume.",
     "expected_tipo": "GUEST_INTEL", "notes": "Posible alergia o sensibilidad. Obsesiva."},

    # 95
    {"id": "EXT-095", "employee": ANDREI,
     "message": "El minibar de una suite no enfría bien.",
     "expected_tipo": "INCIDENCIA", "notes": "Falla técnica. Sin número de suite."},

    # 96
    {"id": "EXT-096", "employee": SOFIA,
     "message": "El instructor de yoga y la huésped sueca desaparecieron juntos después del sunset.",
     "expected_tipo": "NO_REPORTE", "notes": "Gossip sin valor operacional."},

    # 97
    {"id": "EXT-097", "employee": MIGUEL,
     "message": "Mesa 18. Cliente pidió café descafeinado doblemente confirmado por sensibilidad a cafeína.",
     "expected_tipo": "GUEST_INTEL", "notes": "Sensibilidad confirmada. Obsesivo con doble verificación."},

    # 98
    {"id": "EXT-098", "employee": RAUL,
     "message": "Huésped quería alquilar barco o algo parecido para mañana.",
     "expected_tipo": "GUEST_INTEL", "notes": "Solicitud pendiente. Distraído: sin datos del huésped."},

    # 99
    {"id": "EXT-099", "employee": CARMEN,
     "message": "La señora del detox pidió hamburguesa escondida por delivery.",
     "expected_tipo": "NO_REPORTE", "notes": "Anécdota sin valor operacional para el hotel."},

    # 100
    {"id": "EXT-100", "employee": LAURA,
     "message": "Habitación 321. Cliente celebra aniversario número 25. Solicita pétalos rojos únicamente, no rosados.",
     "expected_tipo": "GUEST_INTEL", "notes": "OCASION con detalle de color específico. Típico obsesivo."},
]
