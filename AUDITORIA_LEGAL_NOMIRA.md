# Auditoría legal y de privacidad de Nomira (base para el abogado)

- **Fecha de la revisión del código:** 19 de noviembre de 2026, sobre la rama `main` del repositorio `jorjavku-coder/nomira`, versión con los módulos Nómina, Evidencia, AFORE, Leads y Academia.
- **Fecha de consulta de la legislación:** 19 de noviembre de 2026. Las fuentes están en la sección 10.
- **Alcance:** solo se revisó el código, la configuración del repositorio y su documentación (`README.md`, `render.yaml`). No se revisaron contratos, cuentas de proveedores, el panel de Render ni la base de datos de producción.
- **Exclusiones:** en este informe no se reproducen secretos, contraseñas, llaves ni datos de clientes.

Este documento **no es un dictamen jurídico** ni un aviso de privacidad. Es un inventario técnico verificable para que un abogado mexicano redacte o revise los documentos legales.

## Cómo leer las etiquetas

| Etiqueta | Significado |
|---|---|
| **[Código]** | Confirmado en el código fuente o en las pruebas automáticas del repositorio. |
| **[Doc]** | Aparece en la documentación o en comentarios de configuración, pero no se puede comprobar desde el código. |
| **[No verificable]** | No se puede confirmar desde el repositorio. Lo debe responder el fundador (sección 8). |

---

## 1. Descripción de la empresa y del producto (solo lo confirmado)

### Empresa

- **No hay datos verificables:** el repositorio no contiene razón social, RFC, domicilio, correo legal ni datos fiscales de la empresa que opera Nomira. **[No verificable]**
- **Pie de página:** el sitio muestra «© Nomira · Desarrollado por IMA». **[Código]** No se pudo verificar qué es «IMA» ni su relación jurídica con Nomira.
- **Dominio:** el dominio público configurado es `nomirasoft.com`. **[Doc]**

### Producto

Nomira es una aplicación web (SaaS) para despachos y áreas jurídicas. Cada cliente es una **organización** con sus propios usuarios. **[Código]**

Los módulos existen en `backend/app/services/modulos.py` y se habilitan **por separado** para cada organización. **[Código]**

| Módulo | Qué hace (según el código) |
|---|---|
| **Nómina y prestaciones** | Lee recibos de nómina en PDF (texto u OCR local con Tesseract), suma percepciones según un catálogo de claves y exporta a Excel y PDF. Tiene una verificación opcional con IA, apagada por omisión. |
| **Nomira Evidencia** | Asuntos con documentos, lectura de hechos y fechas, diferencias entre fuentes y cronología. Incluye un **enlace seguro para que el cliente del despacho suba documentos** (con código por correo). |
| **Nomira AFORE** | Casos AFORE/SAR. Guarda CURP y NSS **cifrados**, consentimientos del cliente, documentos y plazos. Tiene un **portal del cliente** y mensajes por WhatsApp Business Platform (opcional, con aprobación humana). La consulta de CURP oficial es opcional y hoy no está configurada. |
| **Nomira Leads** | Prospectos del despacho: etapas, próximos pasos, consentimientos y campañas. Recibe prospectos por formulario público, WhatsApp, anuncios de Meta e integraciones (Zapier, Make, Google Ads). |
| **Nomira Academia** | Cursos internos del despacho, avance, cuestionarios y constancias de participación en PDF. |

**Funciones transversales [Código]:**

- Panel de la plataforma (`/plataforma`) para quien opera Nomira: alta de clientes, módulos, suscripciones, soporte y solicitudes de informes. El panel **no da acceso** a expedientes ni a documentos de los clientes.
- Bitácora de auditoría.
- Soporte por tickets.
- Correos transaccionales (bienvenida, vencimiento y códigos).
- Formulario público de informes en el sitio web.

**Cobro:**

- No hay pasarela de pago en el código.
- Las suscripciones se registran a mano (plan, fechas, monto, «pagado») en `periodos_suscripcion`. **[Código]**
- No hay renovación automática ni emisión de CFDI en el código. **[Código]**

**Registro:**

- El autoregistro está desactivado por omisión (`PERMITIR_REGISTRO`). **[Código]**
- Hoy, quien opera Nomira da de alta a los despachos. Después, cada administrador del despacho crea a sus propios usuarios. **[Código]**

---

## 2. Inventario de datos tratados

Para todas las categorías aplican estas reglas comunes:

- **Base de datos:** todo se guarda en la base PostgreSQL del servicio. **[Código]**
- **Archivos:** los archivos subidos se guardan en disco, en la carpeta `STORAGE_DIR`, separados por organización. **[Código]**
- **Hosting:** según `render.yaml`, el servicio corre en Render. **[Doc]** Además, el comentario del propio archivo dice que el despliegue actual es de **demostración en plan gratuito**: el disco es temporal y la base de datos gratuita caduca a los 30 días («No lo use con datos reales»). **[Doc]**
- **Conservación:** **no hay plazos automáticos de borrado** en el código para ninguna categoría. Los datos se conservan hasta que alguien los elimina (ver sección 6). **[Código]**

### 2.1 Datos de cuenta y usuarios del despacho

- **Datos:** nombre de la organización, logotipo, estado (activa o suspendida). Por cada usuario: nombre, correo, contraseña (solo su *hash* bcrypt), rol (administrador, analista o consulta), foto de perfil, fecha de alta y baja lógica. **[Código]**
- **Quién parece decidir:** Nomira, para prestar el servicio. Los usuarios los da de alta el administrador del despacho.
- **Dónde se captura:** panel de la plataforma (alta del cliente), «Usuarios» en la app y «Mi perfil».
- **Quién lo ve:**
  - Los usuarios de la misma organización (la lista de usuarios).
  - Quien opera Nomira ve los clientes y sus administradores en el panel de la plataforma.
- **Conservación:** la baja de un usuario es **lógica**, es decir, no borra su registro. Solo se borra al eliminar toda la organización.
- **Proveedores:** hosting. El correo de bienvenida pasa por el proveedor de correo.

### 2.2 Facturación y suscripciones

- **Datos:** plan, fechas de inicio y fin, monto, si está pagado y una nota. **No** hay datos de tarjeta, datos bancarios ni RFC del cliente en el código. **[Código]**
- **Quién parece decidir:** Nomira.
- **Dónde se captura:** a mano en el panel de la plataforma.
- **Quién lo ve:** quien opera Nomira.
- **Proveedores:** ninguno de pagos. **[Código]**

### 2.3 Soporte

- **Datos:** tickets y mensajes entre el despacho y Nomira (texto libre, que puede incluir datos personales si el usuario los escribe). **[Código]**
- **Quién parece decidir:** Nomira.
- **Dónde se captura:** «Soporte» en la app y en el panel.
- **Quién lo ve:** los usuarios de la organización y quien opera Nomira.

### 2.4 Marketing y prospectos de Nomira (sitio web)

- **Datos:** formulario «Solicitar informes» con tipo, nombre, empresa, correo, teléfono, volumen aproximado, mensaje, **dirección IP** y la casilla de aceptación de contacto. Se guarda en `solicitudes`. **[Código]**
- **Botón de WhatsApp:** el sitio tiene un botón (`wa.me`) que abre WhatsApp del visitante. Nomira no recibe datos por esa vía. **[Código]**
- **Quién parece decidir:** Nomira.
- **Quién lo ve:** quien opera Nomira, en el panel.
- **Proveedores:** hosting.
- **Lo que no hay:** envío de boletines, campañas de marketing de Nomira ni analítica. **[Código]**

### 2.5 Información de los clientes de los despachos

En los módulos de trabajo, el **despacho parece decidir** las finalidades y Nomira trata los datos por su cuenta. Es decir, Nomira actuaría como **persona encargada** en el sentido del artículo 2, fracción XII de la LFPDPPP 2025. Esto debe confirmarlo el abogado y quedar en un contrato.

| Módulo | Datos (según el código) | Dónde se capturan | Quién los ve |
|---|---|---|---|
| Nómina | Recibos de nómina en PDF y su texto: trabajador, CURP, RFC, NSS, plaza, percepciones, deducciones e importes (**laborales y patrimoniales**). | Carga de PDF en la app. | Usuarios de la organización. |
| Evidencia | Asuntos (cliente, jurisdicción, expediente judicial), **cualquier documento** que suba el despacho o su cliente, hechos y fechas extraídos, correo del cliente para la solicitud de documentos. | App; enlace `/subir` con código enviado por correo. | Usuarios de la organización. Algunos documentos pueden quedar restringidos. |
| AFORE | Nombre, teléfono, correo, **CURP y NSS (cifrados)**, relación con el titular, consentimientos, documentos, folios, mensajes de WhatsApp y accesos al portal. | App; portal `/portal`; WhatsApp. | Usuarios de la organización. CURP y NSS se muestran enmascarados y revelarlos queda en la bitácora. El cliente ve en el portal solo lo que se publica. |
| Leads | Nombre, teléfono, correo, ciudad, materia, descripción de su problema, consentimientos (con fecha, medio y revocación), mensajes, origen (UTM o anuncio) y datos de formularios de Meta o Google. | App; formulario público `/contacto`; WhatsApp; webhooks de Meta; entrada para Zapier, Make y Google Ads. | Usuarios de la organización. El rol «consulta» ve el teléfono y el correo enmascarados. |
| Academia | Avance, respuestas, calificaciones y folio de constancia de los **usuarios del despacho**. | App. | La persona, los administradores y los instructores. |

### 2.6 Datos sensibles que podrían aparecer

El código **no clasifica ni filtra** el contenido de los documentos. **[Código]** Por la naturaleza de un despacho, en Evidencia, AFORE y Leads pueden aparecer:

- datos de **salud** (incapacidades, dictámenes);
- datos de **menores**;
- vida familiar (divorcios, pensiones);
- origen étnico;
- datos penales;
- datos **financieros y patrimoniales** (estados de cuenta AFORE, recibos).

La LFPDPPP 2025 exige consentimiento **expreso y por escrito** para datos sensibles (art. 8) y **expreso** para datos financieros o patrimoniales (art. 7), salvo las excepciones del art. 9.

### 2.7 Cookies, almacenamiento local, analítica y registros técnicos

**Cookies:**

- El código de Nomira **no crea cookies**. No hay `set_cookie` en el backend ni `document.cookie` en el frontend. **[Código]**
- El proxy de Render o Cloudflare podría crear cookies técnicas. **[No verificable]**

**Almacenamiento en el navegador [Código]:**

- La sesión de la app (token y datos básicos del usuario) se guarda en `sessionStorage`. Se borra al cerrar la pestaña.
- El portal del cliente y la subida de documentos guardan su enlace temporal en `sessionStorage`.
- La preferencia de modo claro u oscuro del sitio se guarda en `localStorage`. Es funcional, no de rastreo.

**Lo que no se encontró en el código [Código]:**

- Google Analytics, píxeles, Sentry u otras herramientas de analítica o publicidad.
- Fuentes descargadas de Google: las fuentes van incluidas en el propio sitio (`@fontsource`).

**Contenidos de terceros:** las lecciones de Academia pueden incrustar videos de YouTube (dominio `youtube-nocookie.com`) o Vimeo, si el despacho los agrega. **[Código]**

**Registros técnicos:**

- La tabla `auditoria` guarda usuario, **correo**, acción, entidad, detalle e **IP**. No tiene plazo de borrado. **[Código]**
- `correos_enviados` guarda el tipo, los destinatarios, el asunto y el estado. **[Código]**
- Los registros del servidor (stdout de Render) contienen en algunos mensajes **correos o nombres**: por ejemplo, el aviso «No se envió el correo … a …» y el nombre del cliente en los recordatorios. **[Código]**
- La retención de esos registros en Render no es verificable. **[No verificable]**

---

## 3. Resumen por categoría

| Categoría | ¿Quién parece decidir? | Captura | Almacenamiento | Acceso | Conservación | Pueden recibirla |
|---|---|---|---|---|---|---|
| Cuentas y usuarios | Nomira | Panel y app | PostgreSQL | Organización y operador | Sin plazo; baja lógica | Hosting; correo (Resend o SMTP) |
| Suscripciones | Nomira | Panel | PostgreSQL | Operador | Sin plazo | Hosting |
| Soporte | Nomira | App y panel | PostgreSQL | Organización y operador | Sin plazo | Hosting; correo |
| Prospectos de Nomira | Nomira | Sitio web | PostgreSQL (con IP) | Operador | Sin plazo | Hosting |
| Datos de clientes del despacho (Nómina, Evidencia, AFORE, Leads) | Despacho (Nomira, como encargada) | App, `/subir`, `/portal`, `/contacto`, webhooks | PostgreSQL y disco | Solo la organización | Sin plazo; borrado manual | Hosting; correo (códigos); Meta (si el despacho conecta WhatsApp o anuncios); Anthropic (solo si se activa la IA); proveedor de CURP (si se configura) |
| Academia | Despacho | App | PostgreSQL y disco | Organización | Sin plazo | Hosting; YouTube o Vimeo (si se incrustan) |
| Bitácora y registros | Nomira y despacho | Automático | PostgreSQL y stdout | Organización y operador | Sin plazo | Hosting |

---

## 4. Mapa de proveedores y posibles subencargados

| Proveedor | Para qué | Evidencia | Dudas |
|---|---|---|---|
| **Render** | Hosting del servicio web y de PostgreSQL. | `render.yaml` **[Doc]** | Región, plan contratado, respaldos y términos. El archivo indica **plan gratuito de demostración**. **[No verificable]** |
| **Cloudflare** | Proxy delante de Render. | Solo un comentario en `render.yaml` **[Doc]** | No hay contrato directo con Nomira. Cookies y ubicación. **[No verificable]** |
| **Resend** | Envío de correos (bienvenida, recordatorios, códigos y respuestas de Leads). | `services/correo.py` llama a `api.resend.com` **[Código]** | Cuenta, región y términos. Si está activo en producción. **[No verificable]** |
| SMTP genérico | Alternativa de correo. | `services/correo.py` **[Código]** | Si se usa. |
| **Anthropic** | Lectura opcional de imágenes de recibos con IA. **Envía imágenes de recibos de nómina** al proveedor. | `services/ia_adaptador.py`; `IA_HABILITADA=false` por omisión **[Código]** | Si está activado en producción; términos de retención y entrenamiento; país. **[No verificable]** |
| **Meta (WhatsApp Business Platform y Lead Ads)** | Mensajes de AFORE y Leads; recepción de prospectos de anuncios. | `services/afore/whatsapp.py`, `services/leads/meta.py` **[Código]** | Solo opera si cada despacho conecta **su propia** cuenta y el servidor tiene configurado el secreto de la app. ¿Quién es titular de la app de Meta? **[No verificable]** |
| Proveedor de validación de CURP | Consulta oficial de CURP. | `services/afore/curp_oficial.py` (URL configurable, sin nombre) **[Código]** | Hoy aparece «no configurada». **[No verificable]** |
| Google Ads, Zapier, Make | **Envían** prospectos a Nomira; Nomira no les envía datos. | `routers/leads_publico.py` **[Código]** | Los contrata el despacho, no Nomira. |
| YouTube y Vimeo | Videos incrustados en Academia. | `routers/academia.py` **[Código]** | Solo si el despacho los usa. |
| GitHub | Código fuente. | Repositorio | No debería contener datos personales. |
| Proveedor del dominio y DNS (cPanel) | DNS de `nomirasoft.com` y registros de Resend. | Configuración externa, no en el código. | **[No verificable]** |

Un SDK en el código no prueba que haya un contrato. Por ejemplo, `anthropic` es una dependencia opcional que solo se usa si se activa la IA.

---

## 5. Flujos de datos

```
Visitante del sitio ── formulario de informes ──► Nomira (solicitudes, con IP)
Visitante ── botón WhatsApp ──► WhatsApp del visitante (Nomira no recibe nada)

Nomira (operador) ── alta del cliente ──► Organización + administrador ── correo de bienvenida ──► Resend
Administrador del despacho ── crea usuarios ──► Nomira

Abogado/usuario ── sube recibos y documentos ──► Nomira (BD + disco)
                  └─ (opcional, IA activada) ── imagen del recibo ──► Anthropic

Cliente del despacho ◄── enlace /subir + código por correo (Resend) ── Despacho
Cliente del despacho ── sube documentos ──► Nomira (pendiente de revisión del despacho)
Cliente del despacho ◄── portal AFORE /portal (lo que el despacho publica) ── Nomira

Prospecto del despacho ── /contacto, WhatsApp, Meta Lead Ads, Zapier/Make/Google Ads ──► Nomira (Leads)
Despacho ── mensaje aprobado por una persona ──► Meta (WhatsApp) o Resend (correo) ──► Cliente o prospecto

Despacho ── consulta CURP (si se configura) ──► Proveedor de CURP
```

---

## 6. Controles verificables

| Control | Estado | Evidencia y observaciones |
|---|---|---|
| Roles y permisos | **Confirmado** | Roles administrador, analista y consulta, verificados en el servidor (`deps.py`). En Academia hay además instructores. Las pruebas automáticas cubren permisos. |
| Aislamiento por organización | **Confirmado** | Todas las consultas filtran por `organizacion_id`; hay pruebas de aislamiento en cada módulo. |
| El operador no ve expedientes | **Confirmado** | La sesión de la plataforma usa otra audiencia de JWT y no sirve en la API de clientes. Hay una prueba automática. |
| Autenticación | **Confirmado** | Contraseñas con bcrypt (12 rondas); JWT HS256 de 8 horas; las sesiones se invalidan al cambiar la contraseña o desactivar al usuario. |
| Freno contra fuerza bruta | **Parcial** | Existe, pero se guarda **en memoria**: se reinicia con el servidor y no se comparte entre instancias. |
| Bitácora | **Parcial** | Registra acciones relevantes con usuario, IP y fecha. No es inmutable y no tiene plazo de conservación. |
| Cifrado de datos sensibles | **Parcial** | CURP, NSS y tokens de WhatsApp y Meta se cifran con Fernet. Los documentos, los recibos y el resto de la base **no** se cifran a nivel de aplicación. |
| Cifrado en tránsito (HTTPS) | **No verificable** | Lo da el hosting; no se configura en el código. |
| Cifrado en reposo (disco y base de datos) | **No verificable** | Depende de Render y del plan. |
| Respaldos | **No verificable** | No hay respaldos en el código. El plan gratuito descrito en `render.yaml` tiene una base que caduca. |
| Exportación | **Parcial** | Hay exportaciones por módulo (Excel, CSV y PDF). No hay exportación completa de la cuenta. |
| Eliminación | **Parcial** | Se pueden borrar documentos y expedientes, y eliminar la organización completa (borra la base y los archivos). Los usuarios solo tienen baja lógica. En Leads se puede anonimizar. |
| Retención | **No verificable** | No hay plazos ni borrado automático. |
| Recuperación ante desastres | **No verificable** | No está documentada. |
| Gestión de incidentes y aviso de vulneraciones | **No verificable** | No hay procedimiento en el código ni en la documentación. |
| Canal ARCO | **No existía** | No había canal ni registro. Se implementó en esta misma entrega (ver «Centro Legal»), pero **requiere un procedimiento interno**. |
| Evidencia de aceptación de términos | **No existía** | Se implementó en esta misma entrega. |

---

## 7. Riesgos legales y de privacidad priorizados

Este análisis no afirma que Nomira incumpla ninguna norma. Señala riesgos según la evidencia disponible.

| # | Riesgo | Impacto | Probabilidad | Comentario |
|---|---|---|---|---|
| 1 | Operar con datos reales en un despliegue descrito como **demostración en plan gratuito** (disco temporal y base que caduca). | Alto | **Por confirmar** | Posible pérdida de documentos y datos. Afecta el deber de seguridad (art. 18) y lo que se pueda prometer en los términos. Hay que confirmar el plan real en Render. |
| 2 | No había aviso de privacidad, términos ni contrato de encargo con los despachos. | Alto | Alta | Los arts. 15 y 16 exigen un aviso al recabar datos. La relación responsable–encargada debe documentarse. |
| 3 | Datos sensibles y financieros en documentos subidos, sin clasificación. | Alto | Media | El despacho, como responsable, debe obtener el consentimiento (arts. 7 y 8). Nomira debe garantizar sus medidas como encargada. |
| 4 | Envío de imágenes de recibos a un proveedor de IA extranjero si se activa la IA. | Alto | **Por confirmar** | Hay que revelarlo, analizar si es una remisión o una transferencia (art. 35) y revisar los términos de entrenamiento y retención. |
| 5 | Proveedores probablemente fuera de México (hosting, correo, Meta). | Medio | Alta | Hay que informarlo en el aviso y en el contrato con los despachos. La ubicación no se pudo verificar. |
| 6 | Correos y nombres en los registros del servidor; IP en la bitácora y en las solicitudes, sin plazo. | Medio | Alta | Proporcionalidad y conservación (art. 5). |
| 7 | No hay procedimiento ni responsable para solicitudes ARCO. | Medio | Alta | El art. 29 exige designar a una persona o departamento; el art. 31 fija plazos en días hábiles. |
| 8 | No hay política de retención, eliminación ni respaldos. | Medio | Alta | La baja de usuarios es lógica y no hay plazos. |
| 9 | Sin procedimiento de vulneraciones. | Medio | Media | El art. 19 exige informar de inmediato al titular cuando la afectación es significativa. |
| 10 | Mensajería de WhatsApp y Meta de los despachos. | Medio | Media | Hay que definir contractualmente quién es responsable del consentimiento y del cumplimiento de las políticas de Meta. |
| 11 | Venta a personas consumidoras (si ocurre). | Medio | **Por confirmar** | La LFPC, art. 76 Bis, fue reformado el 12-12-2025 (cancelación de suscripciones y aviso de renovaciones). Hoy no hay cobro automático. |
| 12 | Freno de acceso solo en memoria. | Bajo | Media | Es una medida de seguridad mejorable. |

---

## 8. Preguntas para el fundador (antes de redactar)

1. **Datos de la empresa:** razón social, RFC, domicilio legal y representante. ¿Qué es «IMA» y qué relación tiene con Nomira?
2. **Contacto:** correo de privacidad y contacto legal. ¿Quién es la persona o el departamento de datos personales (art. 29)?
3. **Ubicación:** ¿en qué países se alojan y procesan los datos? ¿Qué región y qué plan de Render se usan **hoy en producción**? ¿Tiene respaldos contratados?
4. **Proveedores:** ¿cuáles están **realmente contratados** (Render, Resend, Anthropic, la app de Meta, un proveedor de CURP)? ¿Ya revisó o aceptó sus términos y sus acuerdos de tratamiento de datos?
5. **IA:** ¿está activada en producción (`IA_HABILITADA`)? ¿El proveedor usa los datos para entrenar modelos? ¿Nomira lo permitirá alguna vez?
6. **Conservación:** ¿cuánto tiempo se guardan los datos después de cancelar el servicio? ¿Cómo se entregan o se borran? ¿Cuánto tiempo se guardan la bitácora y las solicitudes de informes?
7. **Cobro:** política de cobro, renovación, cancelación y reembolsos. ¿Se emiten CFDI? ¿Habrá cobro automático?
8. **Clientes:** ¿se vende **solo** a empresas y despachos, o también a personas físicas que serían consumidoras?
9. **Controversias:** jurisdicción, ley aplicable y forma de resolverlas.
10. **Seguridad:** ¿qué medidas **puede demostrar** Nomira (además de las del código): respaldos, acceso restringido al servidor, cifrado del proveedor, pruebas de seguridad, capacitación?
11. **Contrato con los despachos:** ¿Nomira firmará un contrato o anexo de encargo de tratamiento con cada despacho? ¿Quién atiende las solicitudes ARCO de los clientes de un despacho? (Deberían ir al despacho, que es el responsable.)
12. **Marketing:** ¿Nomira enviará boletines o promociones a sus prospectos o usuarios? Si lo hará, se necesita una finalidad secundaria y un mecanismo para negarse.
13. **Versiones:** ¿qué cambios de los documentos exigirán una nueva aceptación?

---

## 9. Documentos legales necesarios

| Documento | ¿Depende de las respuestas? |
|---|---|
| **Términos y condiciones del servicio** (SaaS B2B) | Sí: preguntas 1, 7, 8, 9 y 10. |
| **Aviso de privacidad integral** de Nomira como responsable (usuarios, soporte, prospectos e informes) | Sí: preguntas 1 a 6 y 12. |
| **Aviso de privacidad simplificado** (para formularios, art. 16) | Sí: se deriva del integral. |
| **Política de cookies y tecnologías similares** (hoy solo almacenamiento técnico y funcional, sin analítica) | Sí: preguntas 3 y 4 (cookies de Cloudflare o Render). |
| **Anexo o contrato de encargo de tratamiento** con cada despacho (Nomira como encargada, lista de subencargados, seguridad, vulneraciones, devolución y borrado) | Sí: preguntas 3 a 6, 10 y 11. |
| Lista pública de **subencargados** | Sí: pregunta 4. |
| **Procedimiento interno ARCO** y designación de responsable | Sí: pregunta 2. |
| **Política de retención, eliminación y respaldos** | Sí: preguntas 3 y 6. |
| **Procedimiento de vulneraciones e incidentes** | Sí: pregunta 10. |
| Política de uso aceptable (lo que el despacho no debe subir o hacer) | Parcialmente. |
| Modelo de aviso de privacidad **para los clientes del despacho** (portal, subida de documentos, formulario `/contacto`), que es responsabilidad del despacho | Sí: pregunta 11. |
| Política de uso de IA | Sí: pregunta 5. |
| Términos para consumidores conforme a la LFPC (solo si se vende a personas físicas) | Sí: pregunta 8. |

---

## 10. Fuentes legales consultadas (19-11-2026)

- **LFPDPPP:**
  - Nueva ley publicada en el DOF el **20-03-2025**, con última reforma del **14-11-2025** (homologación con el Código Nacional de Procedimientos Civiles y Familiares).
  - Cámara de Diputados, texto vigente: https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf
  - Historial de reformas: https://www.diputados.gob.mx/LeyesBiblio/ref/lfpdppp.htm
  - Artículos citados: 2 (definiciones, incluida la persona encargada), 5 (principios), 7 a 9 (consentimiento y excepciones), 15 y 16 (aviso integral y simplificado), 18 y 19 (seguridad y vulneraciones), 27 a 34 (ARCO; plazos de 20 y 15 días hábiles), 35 y 36 (transferencias) y 58 y 59 (sanciones).
- **Autoridad:** las funciones del extinto INAI sobre datos en posesión de particulares pasaron a la **Secretaría Anticorrupción y Buen Gobierno** (decreto DOF 20-03-2025: https://dof.gob.mx/nota_detalle.php?codigo=5752569&fecha=20/03/2025).
- **Reglamento de la LFPDPPP (DOF 21-12-2011):**
  - Sigue publicado como texto vigente: https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LFPDPPP.pdf
  - Hay que aplicarlo solo en lo que no contradiga la ley de 2025. **El abogado debe confirmar su alcance.**
- **Código de Comercio**, Título Segundo «Del Comercio Electrónico» (arts. 89 y siguientes), sobre mensajes de datos, y **NOM-151-SCFI-2016** sobre conservación de mensajes de datos (DOF 30-03-2017).
- **Ley Federal de Protección al Consumidor:**
  - Última reforma DOF **12-12-2025** (fracciones VIII y IX del art. 76 Bis, sobre suscripciones y cancelación): https://www.diputados.gob.mx/LeyesBiblio/ref/lfpc.htm
  - Solo es relevante si se vende a personas consumidoras.

No se usaron plantillas anteriores a la ley de 2025 como autoridad. Las referencias al INAI en documentos anteriores deben actualizarse.
