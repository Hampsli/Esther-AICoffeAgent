# Esther: Agente de Gestión Técnica - Lily's Bakery & Coffee

Esther es un bot de Telegram diseñado para la automatización de flujos operativos, control de inventarios y gestión administrativa centralizada. El sistema actúa como puente entre el lenguaje natural de los usuarios y bases de datos estructuradas en la nube.

## Especificaciones Técnicas
- **Núcleo:** Python 3.11+ utilizando `python-telegram-bot`.
- **Inteligencia Artificial:** Integración con Ollama (Modelo Qwen 2.5) para procesamiento de lenguaje natural (NLP) y respuesta dinámica.
- **Persistencia de Datos:** Google Sheets API v4 para registros de inventario, asistencia y pedidos.
- **Almacenamiento de Archivos:** Google Drive API v3 para la gestión de documentos y evidencias multimedia.
- **Infraestructura:** Contenerización mediante Docker para asegurar la portabilidad y el aislamiento de dependencias.

## Funcionalidades Operativas

### 1. Control de Inventario
- **Estructura de Datos:** Manejo de 8 columnas técnicas (Artículo, Marca, Contenido Original/Total, Cantidad Actual, Unidad de Medida, Categoría, Notas Adicionales y Mínimo).
- **Consultas Naturales:** Capacidad de responder a preguntas específicas sobre existencias (ej. "¿Cuántas cocoas hay?") mediante búsqueda indexada.
- **Visualización Paginada:** Interfaz de usuario con botones para navegar listas de 10 en 10 elementos.
- **Filtros de Auditoría:** Reportes automáticos basados en:
    - Artículos nuevos agregados.
    - Artículos sin actualización en un periodo superior a 5 días.
    - Artículos en nivel crítico (por debajo del mínimo establecido).

### 2. Gestión de Suministros (Órdenes de Compra)
- **Flujo de Captura:** Interfaz secuencial para registro de encargada y lista de productos.
- **Sincronización:** Registro inmediato en Google Sheets y generación de folios únicos de seguimiento.

### 3. Administración de Personal (Quincenas)
- **Cálculo Automático:** Procesamiento de reportes de asistencia basados en rangos de fechas (DD/MM/AAAA).
- **Integración Contable:** Vinculación con hojas de cálculo para el cálculo de nómina y horas trabajadas.

### 4. Registro y Auditoría
- **Link Logger:** Registro automático de URLs compartidas en el chat dentro de una base de datos central.
- **Gestión Drive:** Subida directa de archivos y fotos al repositorio de Google Drive con registro de metadatos del remitente.

## Seguridad y Acceso
- **Control de Roles (RBAC):** Sistema de permisos diferenciado para perfiles 'Admin' (acceso total y reportes) y 'Staff' (operaciones básicas).
- **Autenticación:** Proceso de configuración (`/setup`) protegido por contraseña para el registro de chats autorizados.
- **Trazabilidad:** Sistema de logs exhaustivo para el monitoreo de flujos de conversación y errores de API.