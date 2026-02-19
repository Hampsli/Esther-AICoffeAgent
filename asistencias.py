import os
from datetime import datetime, timedelta, time
from googleapiclient.discovery import build
from google_drive import _get_creds

ASISTENCIAS_SPREADSHEET_ID = os.environ["ASISTENCIAS_SPREADSHEET_ID"]
ASISTENCIAS_SHEET = "Respuestas de formulario 1"
HORAS_TURNO_BASE = 8  # horas de turno normal


def _get_service():
    return build("sheets", "v4", credentials=_get_creds())


def _get_asistencias(fecha_inicio: datetime, fecha_fin: datetime) -> list:
    """Lee registros del Sheet en el rango de fechas dado."""
    service = _get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=ASISTENCIAS_SPREADSHEET_ID,
        range=f"{ASISTENCIAS_SHEET}!A:H"
    ).execute()
    rows = result.get("values", [])[1:]  # skip header

    registros = []
    for row in rows:
        if len(row) < 5:
            continue
        try:
            # Columna D = fecha del registro
            fecha_str = row[3]
            if isinstance(fecha_str, str) and "/" in fecha_str:
                fecha = datetime.strptime(fecha_str.split(" ")[0], "%d/%m/%Y")
            elif isinstance(fecha_str, str) and "-" in fecha_str:
                fecha = datetime.strptime(fecha_str.split(" ")[0], "%Y-%m-%d")
            else:
                continue

            if fecha_inicio <= fecha <= fecha_fin:
                registros.append({
                    "nombre": row[1].split(" - ")[0].strip() if len(row) > 1 else "",
                    "tipo": row[2] if len(row) > 2 else "",
                    "fecha": fecha,
                    "hora": row[4] if len(row) > 4 else "",
                    "duracion": row[5] if len(row) > 5 else "",
                    "autorizo": row[6] if len(row) > 6 else "",
                    "nota": row[7] if len(row) > 7 else "",
                })
        except Exception:
            continue
    return registros


def _parse_hora(hora_str) -> time | None:
    """Convierte string de hora a objeto time."""
    if not hora_str:
        return None
    try:
        if isinstance(hora_str, str):
            partes = hora_str.strip().split(":")
            return time(int(partes[0]), int(partes[1]))
        return None
    except Exception:
        return None


def calcular_quincena(fecha_inicio: datetime, fecha_fin: datetime) -> dict:
    """
    Calcula horas trabajadas por empleado en el período dado.
    Retorna dict con resumen por empleado.
    """
    registros = _get_asistencias(fecha_inicio, fecha_fin)

    # Agrupar por empleado y fecha
    por_empleado = {}
    for r in registros:
        nombre = r["nombre"]
        if nombre not in por_empleado:
            por_empleado[nombre] = {}
        fecha_key = r["fecha"].strftime("%d/%m/%Y")
        if fecha_key not in por_empleado[nombre]:
            por_empleado[nombre][fecha_key] = {"entrada": None, "salida": None, "permisos": []}

        if r["tipo"] == "Hora de entrada":
            por_empleado[nombre][fecha_key]["entrada"] = _parse_hora(r["hora"])
        elif r["tipo"] == "Hora de salida":
            por_empleado[nombre][fecha_key]["salida"] = _parse_hora(r["hora"])
        elif r["tipo"] == "Permisos":
            por_empleado[nombre][fecha_key]["permisos"].append(r)

    # Calcular horas por empleado
    resumen = {}
    for nombre, dias in por_empleado.items():
        horas_totales = 0.0
        dias_trabajados = 0
        dias_permiso = 0
        dias_sin_salida = 0
        detalle = []

        for fecha, datos in sorted(dias.items()):
            entrada = datos["entrada"]
            salida = datos["salida"]
            permisos = datos["permisos"]

            if permisos and not entrada:
                dias_permiso += 1
                detalle.append(f"  {fecha}: Permiso")
                continue

            if entrada and salida:
                dt_entrada = datetime.combine(datetime.today(), entrada)
                dt_salida = datetime.combine(datetime.today(), salida)
                if dt_salida < dt_entrada:
                    dt_salida += timedelta(days=1)
                horas = (dt_salida - dt_entrada).seconds / 3600
                horas_totales += horas
                dias_trabajados += 1
                horas_extra = max(0, horas - HORAS_TURNO_BASE)
                detalle.append(
                    f"  {fecha}: {entrada.strftime('%H:%M')} → {salida.strftime('%H:%M')} "
                    f"= {horas:.1f}h{'  ⚡ +' + str(round(horas_extra, 1)) + 'h extra' if horas_extra > 0 else ''}"
                )
            elif entrada and not salida:
                dias_sin_salida += 1
                detalle.append(f"  {fecha}: {entrada.strftime('%H:%M')} → ⚠️ sin salida")
            elif not entrada and not salida:
                detalle.append(f"  {fecha}: ⚠️ sin registros")

        horas_extra_total = max(0, horas_totales - (dias_trabajados * HORAS_TURNO_BASE))

        resumen[nombre] = {
            "dias_trabajados": dias_trabajados,
            "dias_permiso": dias_permiso,
            "dias_sin_salida": dias_sin_salida,
            "horas_totales": round(horas_totales, 1),
            "horas_extra": round(horas_extra_total, 1),
            "detalle": detalle
        }

    return resumen


def generar_reporte_quincena(fecha_inicio: datetime, fecha_fin: datetime, sheet_service, spreadsheet_id: str, sheet_name: str):
    """Genera una página nueva en el Sheet con el reporte de quincena."""
    resumen = calcular_quincena(fecha_inicio, fecha_fin)

    # Crear la página
    try:
        sheet_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
        ).execute()
    except Exception:
        pass  # ya existe

    rows = [
        [f"Reporte de Quincena: {fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}"],
        [f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"],
        [],
        ["Empleado", "Días Trabajados", "Días Permiso", "Horas Totales", "Horas Extra", "Días sin salida registrada"]
    ]

    for nombre, datos in resumen.items():
        rows.append([
            nombre,
            datos["dias_trabajados"],
            datos["dias_permiso"],
            datos["horas_totales"],
            datos["horas_extra"],
            datos["dias_sin_salida"]
        ])

    rows.append([])
    rows.append(["--- DETALLE POR DÍA ---"])
    for nombre, datos in resumen.items():
        rows.append([nombre])
        for linea in datos["detalle"]:
            rows.append([linea])
        rows.append([])

    sheet_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows}
    ).execute()

    return resumen


def texto_resumen(resumen: dict, periodo: str) -> str:
    """Genera texto legible para mandar por Telegram."""
    lines = [f"📊 *Reporte {periodo}*\n"]
    for nombre, datos in resumen.items():
        lines.append(f"👤 *{nombre}*")
        lines.append(f"  • Días trabajados: {datos['dias_trabajados']}")
        lines.append(f"  • Horas totales: {datos['horas_totales']}h")
        if datos['horas_extra'] > 0:
            lines.append(f"  • Horas extra: ⚡ {datos['horas_extra']}h")
        if datos['dias_permiso'] > 0:
            lines.append(f"  • Permisos: {datos['dias_permiso']} día(s)")
        if datos['dias_sin_salida'] > 0:
            lines.append(f"  • ⚠️ Sin salida registrada: {datos['dias_sin_salida']} día(s)")
        lines.append("")
    return "\n".join(lines)