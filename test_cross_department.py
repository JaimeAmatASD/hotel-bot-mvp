"""
5 casos cruzados: empleado de un departamento reporta tema de otro departamento.
Verifica que la categoría se asigna por contenido del mensaje, no por departamento del empleado.
"""

CROSS_TESTS = [
    {
        "id": "CROSS-01",
        "employee": {"nombre": "Jaime", "departamento": "SPA", "idioma": "es"},
        "message": "Hay una bombilla fundida en el pasillo del segundo piso",
        "expected_tipo": "INCIDENCIA",
        "expected_categoria": "MANTENIMIENTO",
        "notes": "Empleado del Spa reporta tema de mantenimiento",
    },
    {
        "id": "CROSS-02",
        "employee": {"nombre": "Laura", "departamento": "RECEPCION", "idioma": "es"},
        "message": "El jardín de la entrada está muy seco, parece que no se riega bien",
        "expected_tipo": "OBSERVACION",
        "expected_categoria": "JARDINERIA",
        "notes": "Recepcionista reporta tema de jardinería",
    },
    {
        "id": "CROSS-03",
        "employee": {"nombre": "Andrei", "departamento": "MANTENIMIENTO", "idioma": "es"},
        "message": "La señora de la 215 me dijo que es alérgica al gluten cuando subí a arreglar el AC",
        "expected_tipo": "GUEST_INTEL",
        "expected_categoria": None,
        "expected_tipo_nota_huesped": "ALERGIA",
        "notes": "Empleado de mantenimiento captura guest intel",
    },
    {
        "id": "CROSS-04",
        "employee": {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"},
        "message": "El minibar de la 308 hace un ruido raro, como un zumbido",
        "expected_tipo": "INCIDENCIA",
        "expected_categoria": "MANTENIMIENTO",
        "notes": "Camarera de piso reporta falla técnica",
    },
    {
        "id": "CROSS-05",
        "employee": {"nombre": "Miguel", "departamento": "RESTAURANTE", "idioma": "es"},
        "message": "Últimamente la piscina siempre amanece con hojas del jardín flotando, pasa cada mañana antes de que pasen a limpiar",
        "expected_tipo": "OBSERVACION",
        "expected_categoria": None,
        "notes": "Empleado de restaurante reporta patrón de piscina — categoría ambigua (MANTENIMIENTO o JARDINERIA ambas válidas); lo importante es OBSERVACION y no RESTAURANTE",
    },
]
