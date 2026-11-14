# Nomira

*Cada prestación, en claro.* (Nombre provisional anterior: Quincena Clara; la carpeta del proyecto lo conserva.)

MVP de un SaaS en español para analizar comprobantes de nómina (PDF) y calcular prestaciones por
quincena contra un catálogo autorizado, con revisión humana, trazabilidad y exportación a Excel y PDF.

- **Frontend:** Next.js 14 + TypeScript + Tailwind
- **Backend:** Python 3.12 + FastAPI + SQLAlchemy + Alembic
- **Base de datos:** PostgreSQL 16 (importes en `NUMERIC(14,2)`, nunca `float`)
- **Lectura:** PyMuPDF (texto nativo) y Tesseract en español (páginas escaneadas)
- **Exportación:** openpyxl y ReportLab

![Desglose por quincena](docs/capturas/01b-desglose-formato-excel.png)

## 1. Arranque con Docker Compose

Requisitos: Docker con Compose v2.

```bash
cp .env.example .env
```

Edite `.env` y cambie `POSTGRES_PASSWORD` y `JWT_SECRETO` (genere uno con `openssl rand -hex 32`).

```bash
docker compose up --build -d
```

La aplicación queda en <http://localhost:3000>. Las migraciones se aplican solas al arrancar.

Datos de demostración (100 % sintéticos: personas, plazas y recibos ficticios):

```bash
docker compose exec backend python -m scripts.sembrar_demo
```

Usuarios de la demo (contraseña `Demo-Quincena-2025`; cámbiela o desactívelos):
`admin@demo.local`, `analista@demo.local`, `consulta@demo.local`.

Sin demo: en la pantalla de acceso use «Registrar una organización nueva»; después ponga
`PERMITIR_REGISTRO=false` en `.env` y ejecute `docker compose up -d`.

## 1 bis. Demo en línea con Render (sin instalar nada)

`render.yaml` y `Dockerfile.demo` despliegan una demo con datos sintéticos en el plan gratuito de
[Render](https://render.com): suba este proyecto a un repositorio de GitHub, y en Render elija
**New → Blueprint** y seleccione el repositorio. Al terminar, Render muestra la dirección pública.
El plan gratuito se duerme sin uso, su disco es temporal y la base caduca a los 30 días: es solo
para demostración, no para datos reales. **Esta imagen no se pudo construir en el entorno de
desarrollo (sin Docker); no está probada.**

## 2. Pruebas

```bash
docker compose exec backend python -m pytest -q
```

Las pruebas crean y usan una base aparte (`quincena_test`); no tocan sus datos.

El caso de aceptación se prueba siempre con una **réplica sintética** del recibo (mismas claves e
importes, persona ficticia) y con el OCR del catálogo real. Para ejecutarlo además contra su PDF real
(que no está ni debe estar en el repositorio):

```bash
docker compose cp "/ruta/Comprobantes de pago.pdf" backend:/tmp/comprobantes.pdf
```

```bash
docker compose exec -e QC_COMPROBANTES_REALES=/tmp/comprobantes.pdf backend python -m pytest -q tests/test_aceptacion.py
```

## 3. Desarrollo sin Docker

Necesita PostgreSQL 16, Python 3.12, Node 22 y `tesseract-ocr` con `tesseract-ocr-spa`.

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```

```bash
export DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:5432/quincena JWT_SECRETO=$(openssl rand -hex 32)
```

```bash
alembic upgrade head && python -m scripts.sembrar_demo && uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm ci && npm run dev
```

Pruebas locales: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:5432/quincena_test python -m pytest -q`

Recorrido de humo en navegador sobre la demo (requiere Playwright): `node e2e/flujo_demo.mjs http://localhost:3000`

## 4. Flujo de uso

1. **Catálogos** → crear catálogo → «Leer catálogo desde PDF (OCR)». Se crea un **borrador**; las
   entradas dudosas aparecen marcadas. Un administrador las revisa contra el documento fuente y
   **activa** la versión. (La demo trae ya activa una transcripción de referencia.)
2. **Expedientes** → nuevo expediente. Suba ahí mismo los PDF de recibos: Nomira los lee (sin
   guardarlos todavía) y propone nombre, clave de servidor y periodo; usted revisa y confirma. Al
   crear, los PDF se cargan y procesan solos. También puede capturar todo a mano.
   `datos/ejemplos/recibos_sinteticos.pdf` es un archivo ficticio para probarlo.
3. **Documentos** → subir más PDF cuando haga falta. Cada página se clasifica como recibo o
   informativa. Si los recibos cubren más quincenas que el periodo del expediente, se ofrece ampliarlo.
4. **Desglose por quincena** → primera pantalla del expediente, con el mismo formato de la hoja de
   cálculo que se llenaba a mano: Quincena N, periodo, prestaciones autorizadas y TOTAL. El Excel
   exportado incluye esa misma hoja («Formato quincenal»).
5. **Revisión** → lista de quincenas; conceptos incluidos, excluidos (con motivo) y pendientes; visor
   del comprobante original con la fila resaltada; corregir o confirmar lecturas; decidir duplicados.
6. **Validar** → solo sin pendientes. Congela resultado y versión de catálogo.
7. **Exportar** Excel y PDF (marcados PROVISIONAL mientras no se valide).

## 4 bis. Funciones de SaaS

- **Marca de cada cliente:** en **Mi empresa** el administrador sube el logotipo y el nombre de su
  negocio. Aparecen en la barra lateral para todo su equipo y en los reportes de Excel y PDF. El
  logotipo se guarda en la base de datos, recodificado a PNG (se aceptan PNG, JPG y WebP; no SVG).
- **Informes y suscripción:** la página de inicio incluye un formulario público. Las solicitudes
  se guardan y las ve, en **Solicitudes**, quien opera la plataforma: los usuarios cuyo correo esté
  en `CORREOS_PLATAFORMA`. No se envía ningún correo de aviso; hay que revisar la bandeja.
- El sistema se llama Nomira; el crédito «Desarrollado por IMA» va en el pie de página del sitio.

## 5. Reglas de cálculo implementadas

| Regla | Comportamiento |
|---|---|
| Autorización | Solo percepciones cuya clave coincide **exactamente** (texto, con ceros iniciales) con una clave **activa** de la versión de catálogo del expediente. Nunca por parecido de nombre. |
| No se suma | Deducciones, total neto, totales del recibo, encabezados, páginas informativas. |
| Importe ilegible o ausente | Fila **pendiente** (`NULL`), nunca cero. |
| Clave con formato inesperado | Pendiente. Clave válida pero ausente del catálogo: excluida con motivo. |
| Importe negativo | Conserva el signo y exige confirmación humana antes de sumarse. |
| OCR dudoso | Confianza menor a 70: pendiente hasta que alguien corrija o confirme. |
| Retroactivos | Conservan su clave y se asignan a la quincena de pago. No se redistribuyen ni se equiparan a otra clave. La política se imprime en los reportes. |
| Integridad | Si la suma de percepciones leídas no coincide con el «Total de percepciones» impreso, el recibo queda pendiente. |
| Archivo repetido | Mismo SHA-256 en el expediente: se rechaza la segunda carga. |
| Posible duplicado | Mismo trabajador, plaza, periodo y contenido: **no se suma ni se elimina**; lo decide una persona. |
| Complementario | Mismo periodo y plaza con contenido distinto: se suma, pero exige confirmación. |
| Número de recibo | No identifica al recibo (puede repetirse); solo genera un aviso. |
| Otro trabajador | No se mezcla; exige confirmar la exclusión. |
| Varias plazas | Se conservan separadas; hay que decidir «consolidar» o «separar». Separadas, no se presenta un total único. |
| Faltante vs. cero | Sin comprobante = **faltante** (sin importe). Con comprobante y sin claves autorizadas = **$0.00**. Nunca se inventan periodos. |
| Validación | Bloqueada con pendientes; con faltantes exige reconocerlo explícitamente. El resultado validado es una instantánea inmutable. |
| Catálogo | Una versión activa es inmutable. Cambiar el catálogo crea otra versión; los expedientes existentes no cambian salvo acción explícita y auditada. |
| Correcciones | Guardan usuario, fecha, valor anterior, valor nuevo y motivo. La lectura original se conserva. No tocan el catálogo. |

El motor está en `backend/app/services/calculo.py` (funciones puras, sin base de datos).

## 6. Seguridad y privacidad

- Organizaciones, usuarios y roles: **Administrador** (usuarios, catálogos, todo), **Analista**
  (expedientes, cargas, correcciones, validación) y **Consulta** (lectura y descargas).
- Toda consulta, descarga y operación filtra por la organización del usuario; lo ajeno responde 404.
- Contraseñas con bcrypt; sesión por JWT (8 h); freno de intentos de acceso.
- Los PDF originales se guardan en un volumen privado con nombre derivado de su hash; solo se
  entregan a través de la API autenticada. La API no publica puertos fuera de la red de Compose.
- Carga: se valida extensión, firma `%PDF-`, que el PDF abra, tamaño y número de páginas.
- Auditoría de accesos, cargas, descargas, correcciones, validaciones y cambios de catálogo, sin
  datos personales en el detalle ni en los logs.
- El repositorio no contiene comprobantes reales. `datos/catalogo/Prestaciones.pdf` es el catálogo
  de claves (sin datos personales).

> **Aviso sobre el PDF de muestra recibido:** los trazos azules solo tapan la imagen. El nombre,
> CURP, RFC y número de cuenta siguen presentes en la capa de texto y cualquiera puede extraerlos.
> Si esos archivos se comparten con terceros, deben redactarse con una herramienta que elimine el texto.

## 7. Verificación opcional con IA

Apagada por defecto (`IA_HABILITADA=false`); el cálculo completo funciona sin ella y sin enviar nada
fuera. Al activarla (`IA_HABILITADA=true` y `ANTHROPIC_API_KEY`), el expediente muestra el botón
**Verificar con IA**: una segunda lectura independiente de la imagen de cada recibo que se
**compara** con la lectura del sistema.

- Si coinciden, la quincena se marca «IA ✓».
- Si difieren, aparece un pendiente que impide validar hasta que una persona revise el original y
  corrija o confirme el recibo.
- La IA **no modifica importes, no decide qué claves están autorizadas y no suma**. Su salida se
  valida contra un esquema y el contenido del recibo se le entrega como datos, no como instrucciones.
- Un recibo ya verificado no se reenvía; si su lectura cambia, la verificación caduca.
- Privacidad: se envía la **imagen de cada recibo** (con datos personales) al proveedor de IA. Queda
  en auditoría. Tiene costo por uso según el modelo (`IA_MODELO`).

**Probado solo con un cliente simulado**; no se ha ejecutado contra el servicio real.

## 8. Qué se probó y qué no

**Probado en el entorno de desarrollo** (PostgreSQL 16 local, Tesseract 5.3, Python 3.12 con las
versiones fijadas en `requirements.txt`):

- 46 pruebas automatizadas en verde: reglas de cálculo, lectura nativa y por OCR, API completa,
  aislamiento entre organizaciones, roles, exportaciones y caso de aceptación.
- Caso de aceptación contra los **archivos reales**: el recibo del 1 al 15 de diciembre de 2025
  incluye 0102, 0303, 0322, 0512 y 1609 = **10,408.60**; excluye 0136, 0302, 1633 y 1638. Sin discrepancias.
- El PDF real (32 páginas) produce 16 recibos y 16 quincenas; en los 16 la suma de filas leídas
  coincide con los totales impresos de percepciones y deducciones.
- Recorrido en navegador (Chromium) de punta a punta sobre la demo y carga del PDF real de 20 MB.
- Migración Alembic aplicada desde cero y sin diferencias contra los modelos.

**No probado:**

- **Las imágenes Docker no se construyeron ni se ejecutó `docker compose up`**: el entorno de
  desarrollo no tenía daemon de Docker. `docker compose config` valida la sintaxis; los mismos
  comandos se ejecutaron fuera de contenedor. Es lo primero que conviene verificar.
- El adaptador de IA contra el servicio real.
- Carga concurrente, expedientes de 72 quincenas reales y otros formatos de recibo.

## 9. Limitaciones conocidas

- **Un solo formato de comprobante.** El lector se guía por los encabezados
  CLAVE · CONCEPTO · IMPORTE y las etiquetas del formato de muestra. Otros formatos quedarán como
  página sin clasificar o con pendientes; no se leerán mal en silencio, pero requieren un lector nuevo.
- **OCR del catálogo:** en la muestra leyó 123 de 124 claves; la restante salió como `D466` y quedó
  marcada (no se corrige sola). Algunas descripciones tienen erratas de OCR sin marcar: la
  validación humana es obligatoria. `datos/catalogo/prestaciones_referencia.csv` es mi transcripción
  revisada visualmente; **verifíquela** antes de usarla en casos reales.
- **OCR de recibos escaneados:** probado con escaneos sintéticos limpios a 200 dpi. Con escaneos
  torcidos, borrosos o con sellos habrá más filas pendientes. No hay corrección de inclinación.
- **Procesamiento en el mismo proceso** de la API (tareas de fondo, estado persistente, reintentos
  idempotentes). Si el servicio se reinicia a mitad, el documento queda en error reintentable. Para
  volumen alto hace falta una cola de trabajos y ejecutar un solo proceso de API mientras tanto.
- **Reprocesar** un documento descarta las correcciones hechas sobre sus recibos (quedan en bitácora).
- La lista de expedientes recalcula cada expediente al cargarse; habrá que cachear con muchos.
- Sesión en `sessionStorage` con token portador; no hay recuperación de contraseña, 2FA, correo ni
  cifrado en reposo de los PDF (use un volumen cifrado). El freno de accesos vive en memoria.
- Sin HTTPS propio: publique detrás de un proxy con TLS.
- Sin facturación, planes ni límites por organización.
- Se guarda el texto completo de cada página (requisito de trazabilidad), que incluye datos personales.

## 10. Estructura

```
backend/app/services/extraccion.py      texto nativo u OCR -> palabras con coordenadas
backend/app/services/lector_recibos.py  lectura determinista del comprobante
backend/app/services/catalogo_ocr.py    borrador de catálogo desde PDF
backend/app/services/calculo.py         motor de reglas (puro)
backend/app/services/procesamiento.py   estados, errores y reintentos por documento
backend/app/services/exportar.py        Excel y PDF
backend/app/services/ia_adaptador.py    respaldo opcional
backend/app/routers/                    API (auth, catálogos, documentos, expedientes)
backend/app/sinteticos.py               generador de recibos ficticios
backend/alembic/                        migraciones
backend/tests/                          pruebas
frontend/app/                           pantallas (expedientes, catálogos, usuarios)
datos/catalogo/                         catálogo fuente y transcripción de referencia
```
