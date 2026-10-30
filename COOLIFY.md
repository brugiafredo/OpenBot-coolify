# OpenBot en Coolify v4

Este despliegue ejecuta la API y la app compilada en `server`, las rutinas en
`worker` y los Bots en `agent-harness`, que piensa con **tu plan de ChatGPT** (inicio de
sesión con tu cuenta, como en la app de escritorio) y no con una `OPENAI_API_KEY`.
No utiliza `scripts/start.sh`: ese script arranca procesos en el host,
genera secretos locales y selecciona servicios para desarrollo.

## Imágenes en GHCR y orden de despliegue

GitHub Actions compila y publica las imágenes en GHCR; este Compose usa tres
(`openbot-server`, `openbot-agent-computer` y `openbot-supervisor`). El harness usa la
imagen pública oficial `ghcr.io/copilotkit/openbot-agent-langgraph-agui:v0.2.0`, de la
misma versión que el repositorio, así que no hay que publicar nada más. Coolify solo las descarga;
no compila en el servidor de 2 vCPU y 4 GB de RAM. El workflow usa `GITHUB_TOKEN`,
sin añadir secretos, y publica imágenes para `linux/amd64`.

1. Fusiona la PR en `main`.
2. En la pestaña **Actions**, espera a que termine **Build images**. La primera
   ejecución tarda aproximadamente 20-40 minutos; las siguientes suelen ser más
   rápidas gracias a la caché. También puedes lanzarlo con **Run workflow**.
3. Haz públicos los paquetes de GHCR: **Profile -> Packages -> package ->
   Package settings -> Change visibility -> Public**. Los que usa este Compose son
   `openbot-server`, `openbot-agent-computer` y `openbot-supervisor`, bajo
   `ghcr.io/brugiafredo` (`openbot-agent-bot` y `openbot-agent-langgraph` ya no se usan).
   Como alternativa, mantenlos privados y añade las credenciales del registro en
   Coolify, en **Servers -> tu servidor**, dentro de la configuración de registros
   disponible en tu versión. También puedes ejecutar `docker login ghcr.io` en el
   servidor con un PAT con permiso `read:packages` y acceso a los paquetes.
   Con paquetes privados, el host debe estar autenticado también para descargar
   `agent-computer`; comprueba que las credenciales están disponibles para el usuario
   que ejecuta los despliegues de Coolify. No guardes el PAT en el repositorio.
4. En Coolify, pulsa **Reload Compose File** y después **Redeploy**.

Todos los servicios de aplicación usan `pull_policy: always`. `agent-computer` es un
servicio real, con comprobación de salud y volúmenes, y descarga la imagen antes de
que arranque `supervisor`, que depende de él. El supervisor recibe exactamente la
misma `COMPUTER_IMAGE` y utiliza el socket Docker del host para crear los ordenadores
de los Bots. Su código inspecciona y crea contenedores, pero no descarga imágenes:
la descarga previa de Compose es necesaria. No necesita un PAT dentro del contenedor.
Si borras la imagen del host, vuelve a desplegar antes de crear nuevos ordenadores.

Puedes sobrescribir `SERVER_IMAGE`, `COMPUTER_IMAGE`, `SUPERVISOR_IMAGE` y
`HARNESS_IMAGE` en Coolify. Para fijar una versión, usa por ejemplo
`SERVER_IMAGE=ghcr.io/brugiafredo/openbot-server:sha-<SHA completo del commit>` y fija
las otras dos imágenes propias al mismo SHA. `HARNESS_IMAGE` debe seguir siendo una imagen
`agent-langgraph-agui`: el servidor solo enruta los Bots integrados por el plan de ChatGPT
cuando reconoce ese nombre. `migrate`, `server` y `worker` comparten
`SERVER_IMAGE`; el servicio de ordenador y el supervisor comparten `COMPUTER_IMAGE`.
En un fork, Actions utiliza el propietario del repositorio en minúsculas; cambia las
tres variables propias para apuntar a sus paquetes.

## Configuración en Coolify

1. Crea una aplicación desde este repositorio y selecciona el build pack **Docker Compose**.
2. Establece **Base Directory = /** y **Docker Compose Location = /docker-compose.coolify.yml**.
   Guarda y recarga la definición. Si la importación inicial intenta analizar el archivo
   original, cambia la ubicación en la configuración de la aplicación antes de desplegar.
3. En Environment Variables, rellena los valores obligatorios indicados abajo como
   variables de ejecución. No copies los secretos de desarrollo de `.env.example`.
   No hace falta crear `.env`, `egress.env`, `.openbot` ni `.langchain` en el servidor.
4. Asigna el dominio **únicamente a `server`, puerto interno 3001**. Por ejemplo,
   en el campo de dominio de Coolify: `https://openbot.example.com:3001`.
   El usuario abre `https://openbot.example.com`, sin ese puerto. API y app comparten
   origen. No asignes dominios a Postgres, supervisor ni agentes.
5. Configura OAuth antes del primer arranque público. Registra el callback
   `https://openbot.example.com/api/auth/callback/google` (o `microsoft` / `okta`).
6. Sigue el orden de publicación anterior y despliega. Revisa que `migrate` termine con código 0, que `server` esté saludable
   y que `worker` permanezca activo. La primera vez, conecta ChatGPT como se explica en
   la sección siguiente. Comprueba `/health`, el inicio de sesión, un chat,
   una herramienta de navegador y una rutina. Los contenedores de migración terminados
   son normales; el worker no tiene endpoint HTTP de salud.

La [documentación oficial de Coolify](https://coolify.io/docs/applications/builds/docker-compose)
describe la selección del archivo, las variables y el puerto interno del dominio.
El proxy debe poder llegar a `server` por una red interna; comprueba las redes de la
configuración renderizada si aparece un 502. No soluciones esto publicando el socket
Docker o los puertos de los agentes.

## Modelo: tu plan de ChatGPT (sin `OPENAI_API_KEY`)

Igual que la app de escritorio, el Bot `agent-harness` (LangGraph, imagen
`agent-langgraph-agui`) usa la sesión de ChatGPT guardada en
`/root/.langchain/chatgpt-auth.json`, dentro del volumen nombrado `chatgpt-auth`. El
servidor solo recibe `CHATGPT_AUTH_FILE` como indicador y, con él, también hace pensar a los
Bots integrados (`general-assistant` y `knowledge`) a través del harness. El token de
acceso caduca cada hora; el harness lo renueva solo con el refresh token y reescribe el
archivo, por eso vive en un volumen escribible y no en una variable.

Esta instalación tiene **su propia sesión**: no reutilices la de otro equipo (ver Plan B).

### Primer inicio de sesión (una sola vez, sin mover archivos)

0. Si ChatGPT lo pide, activa antes en chatgpt.com **Settings -> Security** la opción de
   autorización con código de dispositivo para Codex (*device code authorization*).
   En cuentas de empresa/Edu puede tener que activarlo un administrador.
1. Despliega. El servicio de un solo uso `chatgpt-login` arranca junto al resto.
2. En Coolify, abre la aplicación -> **Logs** y elige el contenedor `chatgpt-login`.
   Verás:

   ```
   === INICIO DE SESIÓN DE CHATGPT ===
   1. Abre: https://auth.openai.com/codex/device
   2. Introduce el código: XXXX-XXXXX
   ```

3. Abre esa dirección en tu navegador, entra con tu cuenta de ChatGPT, escribe el código y
   aprueba. En unos segundos el log dice `ChatGPT conectado` y el contenedor termina con
   código 0. Si el código caduca (15 minutos), el servicio genera otro automáticamente,
   hasta cuatro veces; después termina y basta con pulsar **Restart** en la aplicación.
4. No hace falta reiniciar nada: el harness lee el archivo en cada respuesta.
   Prueba un chat.

En cada despliegue o reinicio posterior `chatgpt-login` ve que la sesión existe y termina
al instante con código 0; es normal que figure como *exited*. El código de un solo uso
que aparece en el log no es un secreto reutilizable, pero no lo compartas: quien lo
introduzca antes que tú conectaría su cuenta.

### Volver a conectar o cambiar de cuenta

Si los Bots responden con un error de autenticación de ChatGPT (sesión revocada, cambio
de contraseña, cierre de sesión en todos los dispositivos), abre **Terminal** en Coolify,
elige el contenedor `agent-harness`, ejecuta
`rm /root/.langchain/chatgpt-auth.json`, pulsa **Restart** (o **Redeploy**) en la aplicación y repite los
pasos 2-3.

### Plan B: importar un `auth.json` de Codex existente

Solo si el inicio por código no está disponible. Usa el `~/.codex/auth.json` de un equipo
con `codex login` hecho (tu ordenador o el box de Grok Bot):

1. En Coolify -> **Terminal** -> contenedor `agent-harness`, ejecuta
   `cat > /root/.langchain/codex-auth.json`, pega el contenido del archivo, pulsa Intro y
   luego **Ctrl+D**. No lo pegues en ningún chat ni lo guardes como variable de Coolify.
2. Pulsa **Restart** (o **Redeploy**). `chatgpt-login` convierte el archivo al formato del harness, lo
   guarda en `chatgpt-auth.json` y **borra** `codex-auth.json`.
3. Importante: las dos copias comparten la misma sesión y OpenAI rota el refresh token en
   cada renovación, así que la primera que renueve desconecta a la otra. Inmediatamente
   después de importar, borra el `~/.codex/auth.json` de origen (sin `codex logout`, que
   revocaría también la copia del servidor) y vuelve a ejecutar `codex login` en ese
   equipo si lo sigues usando: obtendrá una sesión nueva e independiente.

### Qué cambia sin clave de OpenAI

- Sin `OPENAI_API_KEY` no hay **voz** (usa la API Realtime de OpenAI), y el enrutado
  automático entre Bots cae siempre en el Bot por defecto, como estaba previsto cuando no
  hay clave. El chat, las herramientas, el ordenador y las rutinas usan el plan.
- Se retiran `agent-bot` (solo funcionaba con clave de OpenAI) y el Bot gestionado
  `agent-langgraph` (bun) / *Risk Analyst*; los sustituye `agent-harness`, que aparece
  como Bot con el nombre de `PICKED_HARNESS_NAME` (por defecto `LangGraph`).
- El modelo es `BOT_MODEL` (por defecto `gpt-6.1-sol`). Debe ser un modelo que tu plan
  ofrezca en Codex; los modelos solo-API como `gpt-4o-mini` no funcionan con el plan.
- Límites: cada respuesta consume el cupo de uso de Codex de tu plan de ChatGPT, el mismo
  que gastas en Codex. El acceso desde un servidor usa una integración que
  `langchain-openai` marca como experimental y no oficial: OpenAI puede cambiarla
  (este Compose ya implementa el inicio por código porque la función de la librería dejó
  de funcionar) y su uso queda sujeto a los términos de tu plan.

## CopilotKit Intelligence: sigue siendo necesario

Las librerías `@copilotkit/*` del servidor y la app son código abierto y se ejecutan dentro
de tu instalación; eso no es «usar Copilot». Lo que requiere cuenta es **CopilotKit
Intelligence**, el servicio donde viven los hilos de conversación y por el que pasa el
chat en tiempo real. En este código no es un complemento: el runtime se construye en modo
Intelligence y de él dependen el chat en sí (envío y retransmisión por su gateway), el
historial y los hilos, los grupos y canales, el bloqueo de hilos, las rutinas, la memoria y
Automatic Learning. El servidor se niega a arrancar sin
`CPK_INTELLIGENCE_API_KEY` (o `INTELLIGENCE_API_KEY`). Quitarlo exigiría reescribir el
runtime, el almacenamiento de hilos y la app, no un cambio de configuración.

La opción sin coste es el plan gratuito alojado: 1.000 interacciones al mes por
organización (una interacción es una pregunta respondida; herramientas y llamadas al
modelo dentro de ella no cuentan). La clave es de proyecto y empieza por `cpk-`: créala
en <https://intelligence.copilotkit.ai> -> **API Keys** (o con
`npx copilotkit login` y `npx copilotkit project select`) y guárdala en
`CPK_INTELLIGENCE_API_KEY`. `COPILOTKIT_LICENSE_TOKEN` no hace falta con el servicio
alojado. La edición local gratuita (Developer Edition) es solo para macOS y uso no productivo.

## Variables obligatorias

Los valores vacíos del Compose evitan secretos de ejemplo, pero **no validan la
configuración en Coolify**: hay que rellenarlos antes de desplegar. Los procesos
rechazan varias configuraciones incompletas al arrancar.

| Variable | Valor / finalidad |
| --- | --- |
| `POSTGRES_PASSWORD` | Contraseña nueva. Usa `openssl rand -hex 32`: se inserta también en `DATABASE_URL`, por lo que conviene usar hexadecimal sin caracteres reservados de URL. Usuario y base son `openbot`. |
| `KEY_ENCRYPTION_KEY` | `openssl rand -base64 32`. Debe decodificar a 32 bytes; conserva la misma clave para poder descifrar las credenciales guardadas. |
| `COMPUTER_TOKEN` | Secreto compartido entre servidor, supervisor y ordenadores. |
| `SUPERVISOR_TOKEN` | Secreto para las llamadas del servidor al supervisor. |
| `WORKER_SHARED_SECRET` | Secreto compartido entre servidor y worker. |
| `MANAGED_AGENT_TOKEN` | Secreto para que el servidor llame a `agent-harness`. |
| `AGENT_TOOL_TOKEN` | Secreto para los callbacks de herramientas al servidor. |
| `CPK_INTELLIGENCE_API_KEY` o `INTELLIGENCE_API_KEY` | Clave de proyecto de CopilotKit Intelligence (`cpk-…`); la primera tiene prioridad. Obligatoria: ver la sección anterior. |
| `BETTER_AUTH_URL` | Origen público HTTPS, por ejemplo `https://openbot.example.com`, sin `:3001`. |
| `BETTER_AUTH_SECRET` | Secreto de sesión de al menos 32 caracteres. |
| `INITIAL_ADMIN_EMAILS` | Correos de los administradores iniciales, separados por comas. |
| `TRUSTED_ORIGINS` | Incluye el origen HTTPS de la app; separa varios por comas. Evita los valores locales por defecto del servidor. |
| Un proveedor OAuth completo | Google: `GOOGLE_OAUTH_CLIENT_ID` y `GOOGLE_OAUTH_CLIENT_SECRET`. Microsoft: `MICROSOFT_OAUTH_CLIENT_ID`, `MICROSOFT_OAUTH_CLIENT_SECRET` y, preferiblemente, `MICROSOFT_OAUTH_TENANT_ID` con el GUID de tu directorio. Okta: `OKTA_OAUTH_CLIENT_ID`, `OKTA_OAUTH_CLIENT_SECRET` y `OKTA_OAUTH_ISSUER`. |

No hay variable para el modelo: se conecta con el inicio de sesión de ChatGPT descrito
arriba. **Borra** `OPENAI_API_KEY` si la tenías (con ella el servidor seguiría usando la API
para voz y enrutado) y `COPILOTKIT_LICENSE_TOKEN` si no usas una instalación propia de
Intelligence.

Genera **un valor distinto** para cada token y para `BETTER_AUTH_SECRET`, por ejemplo
con `openssl rand -hex 32`. Guarda los secretos en Coolify, no en Git. No se usan
variables mágicas para que la generación y el formato de la clave de cifrado sean explícitos.

`OPENBOT_SINGLE_USER=false` y `NODE_ENV=production` están fijados en el Compose.
Un despliegue público requiere autenticación. Como alternativa avanzada al OAuth local,
`OPENBOT_ORGANIZATION_AUTH_URL` puede señalar otra instalación OpenBot HTTPS que
verifique la identidad y los roles; consulta `docs/configuration.md` antes de usarla.

## Variables opcionales incluidas

| Variables | Uso / valor predeterminado |
| --- | --- |
| `INTELLIGENCE_API_URL`, `INTELLIGENCE_GATEWAY_WS_URL` | API y gateway de Intelligence; por defecto `https://api.intelligence.copilotkit.ai` y `wss://realtime.intelligence.copilotkit.ai`. Cámbialos juntos para una instalación propia. |
| `INTELLIGENCE_BROWSER_GATEWAY_WS_URL` | Dirección del mismo gateway accesible desde el navegador si difiere de la interna; vacía usa el gateway anterior. |
| `COPILOTKIT_LICENSE_TOKEN` | Solo para una instalación propia de Intelligence que exija licencia; no con el servicio alojado. |
| `OPENBOT_PUBLIC_URL` | Origen público; vacío utiliza `BETTER_AUTH_URL`. |
| `SIGNIN_ALLOWED_EMAIL_DOMAINS` | Lista de dominios admitidos al iniciar sesión. Con Microsoft requiere un tenant concreto; no `common` ni `organizations`. |
| `BOT_MODEL` | Modelo del plan de ChatGPT que usa `agent-harness`; por defecto `gpt-6.1-sol`. |
| `PICKED_HARNESS_NAME` | Nombre visible del Bot del harness; por defecto `LangGraph`. |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Opcionales y **no recomendadas** con el plan: solo las usan la voz y el enrutado del servidor. Los Bots siguen usando el plan. |
| `CLAUDE_CODE_OAUTH_TOKEN` | Credencial alternativa avanzada que lee el servidor; no la combines con el plan de ChatGPT. |
| `COMPUTER_NETWORK` | Nombre real de la red de ordenadores, por defecto `openbot-coolify-computers`. Se usa tanto en `networks.default.name` como en el supervisor. |
| `COMPUTER_NAMESPACE` | Prefijo para los recursos dinámicos del supervisor, por defecto `openbot-coolify`. Usa un valor único por instalación. |
| `COMPUTER_RUNTIME` | Runtime Docker alternativo, por ejemplo `runsc`, solo si está instalado en el host. |
| `COMPUTER_MEMORY_BYTES` | Límite de RAM de cada ordenador dinámico; vacío usa el comportamiento del supervisor. |
| `COMPUTER_BROWSER_MODE` | `headed` por defecto; `headless` reduce necesidades gráficas. Se aplica también a los ordenadores dinámicos. |
| `COMPUTER_MAX_BROWSERS`, `COMPUTER_BROWSER_IDLE_MS`, `COMPUTER_MEMORY_HIGH_PERCENT`, `COMPUTER_TAB_IDLE_MS` | Ajustes del ordenador compartido, con los valores por defecto del programa al dejarlos vacíos. El supervisor actual no reenvía estos cuatro ajustes a los ordenadores dinámicos. |
| `SERVER_IMAGE`, `COMPUTER_IMAGE`, `SUPERVISOR_IMAGE` | Referencias GHCR opcionales, por defecto `ghcr.io/brugiafredo/openbot-<servicio>:latest`. Admiten etiquetas `sha-<SHA completo>`; `COMPUTER_IMAGE` se comparte con el supervisor. |
| `HARNESS_IMAGE` | Imagen de `agent-harness` y `chatgpt-login`; por defecto `ghcr.io/copilotkit/openbot-agent-langgraph-agui:v0.2.0`. |
| `OPENBOT_SERVER_USER` | `1001:1001`; normalmente no hay que cambiarlo. |
| `COMPOSIO_API_KEY` | Activa el broker de integraciones compartido. |
| `CPK_INTELLIGENCE_LEARNING_CONTAINER_ID`, `CPK_INTELLIGENCE_SKILLS_REVISION` | Contenedor de aprendizaje ya provisionado y revisión de skills opcional. El despliegue no ejecuta el setup de aprendizaje de `start.sh`. |
| `DEPLOYMENT_ID`, `AUDIT_RETENTION_DAYS` | Identidad de la instalación en Intelligence y retención del registro de auditoría. |

La referencia completa está en `.env.example` y `docs/configuration.md`. Sin `env_file`,
**añadir una variable en Coolify no garantiza que se pase a todos los contenedores**:
para funciones adicionales (voz, SMS, SCIM, exportación OTLP, etc.) añade explícitamente
su entrada a `environment` del servicio que la necesita. Lo mismo se aplica a
`EGRESS_PROXY` y `EGRESS_PROXY_<BOT>`: añade las entradas a `agent-computer` y
`supervisor`; este último reenvía las claves `EGRESS_PROXY*` a sus ordenadores.

## Diferencias y causa del fallo de importación

El archivo original contiene valores anidados y operadores de sustitución condicional.
Si el extractor de Coolify los interpreta como parte del nombre de una variable,
genera una clave que incumple su validador y falla antes de arrancar los servicios.
Es una explicación compatible con el error observado, no una reproducción confirmada
sin acceso a la versión y los logs de esa instancia. La documentación actual de
Coolify sí contempla anidación; no es una prohibición general de Docker Compose ni
de todas las versiones de Coolify v4.

Esta variante usa exclusivamente referencias simples o con un único valor por defecto:

- Se eliminan las alternativas `OPENAI_CONTAINER_BASE_URL` e `INTELLIGENCE_CONTAINER_*`.
  Usa directamente `OPENAI_BASE_URL`, `INTELLIGENCE_API_URL` y los gateways, con
  direcciones accesibles desde Docker. El gateway del navegador tiene su propia variable.
- El harness se fija a una imagen concreta (`HARNESS_IMAGE`) en lugar de la selección del
  escritorio; el servidor lo recibe como `PICKED_HARNESS_URL=http://agent-harness:4206`
  (autorizado en `AGENT_ENDPOINT_ALLOWED_HOSTS`). Su callback de herramientas es
  `http://server:3001/api/agent-tools/call`. `MANAGED_AGENT_AG_UI_URL` queda vacío.
- En vez del montaje `.langchain` del escritorio, la sesión de ChatGPT vive en el volumen
  `chatgpt-auth` y la crea el servicio `chatgpt-login`.
- `server` y `worker` arrancan sin perfiles; las migraciones bloquean su arranque si fallan.
  Se retiran `agent-bot` y `agent-langgraph`, que exigían una clave de proveedor.
- SPIRE es opcional según el código del supervisor y se omite junto con sus volúmenes,
  sockets y variables. La aplicación funciona **sin identidad de carga SPIFFE** y lo
  informa. No se presenta un token de desarrollo como identidad válida. Restaurarlo
  requiere configurar SPIRE, provisionar un join token válido en el servidor, distribuir
  la confianza y montar el socket correcto en cada ordenador. El agente original usa
  `pid: host`, socket Docker y bootstrap sin verificación inicial: requiere una revisión
  específica; copiar las dos configuraciones y un token arbitrario no completa el alta.

## Redes, persistencia y operación

No se publica ningún puerto del stack en el host. Postgres y worker están en la red
`data`, marcada interna; solo el servidor pertenece también a la red de ordenadores.
El supervisor entrega direcciones de contenedor y no publica puertos dinámicos cuando
`COMPUTER_NETWORK` está configurada. No depende de `COMPOSE_PROJECT_NAME`.
En el Compose renderizado por tu versión de Coolify, verifica que el nombre efectivo
de esa red coincide con `COMPUTER_NETWORK`; los contenedores dinámicos y `server`
deben compartirla. No habilites la conexión de todos los servicios a una red compartida
con otras aplicaciones. Coolify debe conectar el proxy al servicio público.

Para varias instalaciones o previews en el mismo host, cambia **ambos**
`COMPUTER_NETWORK` y `COMPUTER_NAMESPACE`, y utiliza etiquetas de imágenes distintas
si despliegas revisiones diferentes. No cambies esos nombres después sin planificar
la retirada de los recursos anteriores.

Los volúmenes nombrados de Compose guardan Postgres, archivos y perfiles del ordenador
compartido, y la sesión de ChatGPT (`chatgpt-auth`; contiene un refresh token: trátalo como
un secreto y no lo copies a otros servidores). El supervisor crea **otros contenedores y volúmenes fuera del stack**,
con etiquetas propias: Coolify no los elimina ni respalda automáticamente al retirar
la aplicación. Revisa `supervisor/src/names.ts` antes de operaciones de limpieza.
Respalda la base de datos, todos los perfiles y workspaces, y la clave de cifrado;
no uses una limpieza global de Docker para retirar esta instalación. Cambiar solo
`POSTGRES_PASSWORD` en Coolify no cambia la contraseña de una base ya inicializada:
coordina también el cambio del rol en PostgreSQL.

El único bind mount es `/var/run/docker.sock` en el supervisor. Debe existir en el
host Linux y ser accesible para ese contenedor. **Da acceso equivalente a root al
host incluso montado como solo lectura**: permite enviar órdenes de creación de
contenedores. Los ordenadores ejecutan shell y comparten el kernel salvo que configures
un runtime aislado. La división de redes no sustituye el aislamiento del host.
No actives `AGENT_COMPUTER_ALLOW_PRIVATE_HOSTS`: es una excepción local que el
servidor rechaza con `NODE_ENV=production`, y no hace falta para llamar al supervisor.

Las imágenes se compilan en GitHub Actions. Reserva disco para descargarlas y RAM
para ejecutarlas, especialmente Chromium. Cada ordenador activo añade navegadores y consumo
propio. Mide el uso antes de aumentar concurrencia. Los límites de recursos que
apliques al servicio supervisor en Coolify no se heredan por sus contenedores;
`COMPUTER_MEMORY_BYTES` controla la memoria de estos. Un despliegue del stack tampoco
sustituye necesariamente todos los ordenadores ya creados: comprueba la imagen y su
ciclo de vida al actualizar.

## Validación local sin Docker

Ejecuta `python3 scripts/validate-coolify-compose.py` (requiere PyYAML).
Comprueba YAML, nombres, referencias simples sin anidación ni operadores condicionales,
dependencias, coherencia de la red y del plan de ChatGPT (sin `OPENAI_API_KEY` obligatoria,
volumen compartido entre `chatgpt-login` y `agent-harness`, imagen reconocida por el
servidor y ningún `$` en el script de inicio de sesión, que Coolify interpolaría). No ejecuta `docker compose config` y no acredita
un despliegue real, conectividad del proxy, licencia o credenciales de proveedores.
