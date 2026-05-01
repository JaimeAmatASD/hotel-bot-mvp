TEST_CASES = [
    # === INCIDENCIAS (6) ===
    {
        "id": "INC-01",
        "message": "Hay un goteo en el aire acondicionado de la 204",
        "employee": {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "INCIDENCIA",
        "notes": "Habitación específica, falla mecánica clara, prioridad esperada MEDIA"
    },
    {
        "id": "INC-02",
        "message": "Escalera B la bombilla está fundida",
        "employee": {"nombre": "Andrei", "departamento": "MANTENIMIENTO", "idioma": "ro"},
        "expected_tipo": "INCIDENCIA",
        "notes": "Zona pública, baja-media"
    },
    {
        "id": "INC-03",
        "message": "Mancha grande en la alfombra del lobby cerca de recepción",
        "employee": {"nombre": "Carlos", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "INCIDENCIA",
        "notes": "Limpieza zona pública"
    },
    {
        "id": "INC-04",
        "message": "El huésped de la 312 se acaba de resbalar en el baño, hay agua por todos lados, ya está bien pero hay que limpiar urgente",
        "employee": {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "INCIDENCIA",
        "notes": "CRÍTICA esperada, huésped afectado true"
    },
    {
        "id": "INC-05",
        "message": "Falta papel higiénico en la 305",
        "employee": {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "INCIDENCIA",
        "notes": "Faltante, no rotura — debe ser INCIDENCIA, no observación"
    },
    {
        "id": "INC-06",
        "message": "El jacuzzi del spa está echando agua marrón",
        "employee": {"nombre": "Lucía", "departamento": "OTRO", "idioma": "es"},
        "expected_tipo": "INCIDENCIA",
        "notes": "Categoría SPA o MANTENIMIENTO, alta prioridad"
    },

    # === OBSERVACIONES (4) ===
    {
        "id": "OBS-01",
        "message": "Los clientes piden almohadas extra casi todos los días, deberíamos tener más stock",
        "employee": {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "OBSERVACION",
        "notes": "Patrón observado, sugerencia de mejora"
    },
    {
        "id": "OBS-02",
        "message": "El jardín se ve más seco últimamente, quizás necesita más riego",
        "employee": {"nombre": "Pedro", "departamento": "OTRO", "idioma": "es"},
        "expected_tipo": "OBSERVACION",
        "notes": "Tendencia, no urgencia"
    },
    {
        "id": "OBS-03",
        "message": "Las llaves magnéticas se están descargando muy rápido",
        "employee": {"nombre": "Ana", "departamento": "RECEPCION", "idioma": "es"},
        "expected_tipo": "OBSERVACION",
        "notes": "Patrón sin acción inmediata"
    },
    {
        "id": "OBS-04",
        "message": "El desayuno se queda corto los domingos",
        "employee": {"nombre": "Juan", "departamento": "RESTAURANTE", "idioma": "es"},
        "expected_tipo": "OBSERVACION",
        "notes": "Mejora operativa"
    },

    # === GUEST_INTEL (4) ===
    {
        "id": "GI-01",
        "message": "Los de la 302 están de aniversario hoy",
        "employee": {"nombre": "Ana", "departamento": "RECEPCION", "idioma": "es"},
        "expected_tipo": "GUEST_INTEL",
        "notes": "tipo_nota_huesped: OCASION, habitacion_huesped: 302"
    },
    {
        "id": "GI-02",
        "message": "La señora de la 115 me dijo que es alérgica a los mariscos",
        "employee": {"nombre": "Juan", "departamento": "RESTAURANTE", "idioma": "es"},
        "expected_tipo": "GUEST_INTEL",
        "notes": "tipo_nota_huesped: ALERGIA, habitacion_huesped: 115"
    },
    {
        "id": "GI-03",
        "message": "El señor de la 408 viaja con un bebé, necesita cuna",
        "employee": {"nombre": "Ana", "departamento": "RECEPCION", "idioma": "es"},
        "expected_tipo": "GUEST_INTEL",
        "notes": "Frontera con INCIDENCIA (necesita cuna), pero la info principal es sobre huésped → GUEST_INTEL con campos_faltantes pidiendo si la cuna ya se entregó"
    },
    {
        "id": "GI-04",
        "message": "El huésped 220 pidió que no le hagan la habitación antes de las 11",
        "employee": {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "GUEST_INTEL",
        "notes": "tipo_nota_huesped: PREFERENCIA"
    },

    # === NO_REPORTE (2) ===
    {
        "id": "NR-01",
        "message": "Hola buenos días",
        "employee": {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "NO_REPORTE",
        "notes": "Saludo, no es reporte"
    },
    {
        "id": "NR-02",
        "message": "¿Cuándo me toca el descanso?",
        "employee": {"nombre": "Carlos", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "NO_REPORTE",
        "notes": "Pregunta personal del empleado"
    },

    # === MULTILINGÜE (2) ===
    {
        "id": "ML-01",
        "message": "Room 207 toilet is clogged, water is overflowing",
        "employee": {"nombre": "Ana", "departamento": "HOUSEKEEPING", "idioma": "en"},
        "expected_tipo": "INCIDENCIA",
        "notes": "Inglés, CRÍTICA por agua desbordando, descripcion debe ir en español"
    },
    {
        "id": "ML-02",
        "message": "Camera 105 are o problemă cu aerul condiționat, nu funcționează",
        "employee": {"nombre": "Andrei", "departamento": "MANTENIMIENTO", "idioma": "ro"},
        "expected_tipo": "INCIDENCIA",
        "notes": "Rumano, idioma_original: ro, descripcion en español"
    },

    # === EDGE CASES (2) ===
    {
        "id": "EDGE-01",
        "message": "El cuadro del pasillo de la planta 2 está torcido",
        "employee": {"nombre": "Lucía", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "expected_tipo": "INCIDENCIA",
        "notes": "Cosmético, prioridad BAJA — borde con OBSERVACION pero el roadmap lo trata como incidencia menor"
    },
    {
        "id": "EDGE-02",
        "message": "La 302 hizo mucho ruido anoche, se quejó la 304",
        "employee": {"nombre": "Ana", "departamento": "RECEPCION", "idioma": "es"},
        "expected_tipo": "GUEST_INTEL",
        "notes": "tipo_nota_huesped: RIESGO, sobre comportamiento del huésped — borde con INCIDENCIA pero la info clave es sobre el huésped"
    },
]
