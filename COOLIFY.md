# OpenBot en Coolify v4

Este despliegue ejecuta la API y la app compilada en `server`, y las rutinas en
`worker`. No utiliza `scripts/start.sh`: ese script arranca procesos en el host,
genera secretos locales y selecciona servicios para desarrollo.

## Imágenes en GHCR y orden de despliegue

GitHub Actions compila y publica las cinco imágenes en GHCR. Coolify solo las descarga;
no compila en el servidor de 2 vCPU y 4 GB de RAM. El workflow usa `GITHUB_TOKEN`,
sin añadir secretos, y publica imágenes para `linux/amd64`.

1. Fusiona la PR en `main`.
2. En la pestaña **Actions**, espera a que termine **Build images**. La primera
   ejecución tarda aproximadamente 20-40 minutos; las siguientes suelen ser más
   rápidas gracias a la caché. También puedes lanzarlo con **Run workflow**.
3. Haz públicos los cinco paquetes de GHCR: **Profile -> Packages -> package ->
   Package settings -> Change visibility -> Public**. Sus nombres son
   `openbot-server`, `openbot-agent-computer`, `openbot-supervisor`, `openbot-agent-bot`
   y `openbot-agent-langgraph`, bajo `ghcr.io/brugiafredo`.
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

Puedes sobrescribir `SERVER_IMAGE`, `COMPUTER_IMAGE`, `SUPERVISOR_IMAGE`, `BOT_IMAGE`
y `LANGGRAPH_IMAGE` en Coolify. Para fijar una versión, usa por ejemplo
`SERVER_IMAGE=ghcr.io/brugiafredo/openbot-server:sha-<SHA completo del commit>` y fija
las otras cuatro imágenes al mismo SHA. `migrate`, `server` y `worker` comparten
`SERVER_IMAGE`; el servicio de ordenador y el supervisor comparten `COMPUTER_IMAGE`.
En un fork, Actions utiliza el propietario del repositorio en minúsculas; cambia las
cinco variables para apuntar a sus paquetes.

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
   y que `worker` permanezca activo. Comprueba `/health`, el inicio de sesión, un chat,
   una herramienta de navegador y una rutina. Los contenedores de migración terminados
   son normales; el worker no tiene endpoint HTTP de salud.

La [documentación oficial de Coolify](https://coolify.io/docs/applications/builds/docker-compose)
describe la selección del archivo, las variables y el puerto interno del dominio.
El proxy debe poder llegar a `server` por una red interna; comprueba las redes de la
configuración renderizada si aparece un 502. No soluciones esto publicando el socket
Docker o los puertos de los agentes.

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
| `MANAGED_AGENT_TOKEN` | Secreto para llamar a ambos agentes incluidos. |
| `AGENT_TOOL_TOKEN` | Secreto para los callbacks de herramientas al servidor. |
| `CPK_INTELLIGENCE_API_KEY` o `INTELLIGENCE_API_KEY` | Clave de proyecto de CopilotKit Intelligence; la primera tiene prioridad. Intelligence es obligatorio para historial y memoria. |
| `OPENAI_API_KEY` | Necesaria para la instalación predeterminada y para `agent-bot`, que solo usa OpenAI. Un endpoint compatible sin autenticación puede usar `OPENAI_BASE_URL` sin clave. |
| `BETTER_AUTH_URL` | Origen público HTTPS, por ejemplo `https://openbot.example.com`, sin `:3001`. |
| `BETTER_AUTH_SECRET` | Secreto de sesión de al menos 32 caracteres. |
| `INITIAL_ADMIN_EMAILS` | Correos de los administradores iniciales, separados por comas. |
| `TRUSTED_ORIGINS` | Incluye el origen HTTPS de la app; separa varios por comas. Evita los valores locales por defecto del servidor. |
| Un proveedor OAuth completo | Google: `GOOGLE_OAUTH_CLIENT_ID` y `GOOGLE_OAUTH_CLIENT_SECRET`. Microsoft: `MICROSOFT_OAUTH_CLIENT_ID`, `MICROSOFT_OAUTH_CLIENT_SECRET` y, preferiblemente, `MICROSOFT_OAUTH_TENANT_ID` con el GUID de tu directorio. Okta: `OKTA_OAUTH_CLIENT_ID`, `OKTA_OAUTH_CLIENT_SECRET` y `OKTA_OAUTH_ISSUER`. |

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
| `COPILOTKIT_LICENSE_TOKEN` | Solo si tu instalación de Intelligence necesita una licencia adicional. |
| `OPENBOT_PUBLIC_URL` | Origen público; vacío utiliza `BETTER_AUTH_URL`. |
| `SIGNIN_ALLOWED_EMAIL_DOMAINS` | Lista de dominios admitidos al iniciar sesión. Con Microsoft requiere un tenant concreto; no `common` ni `organizations`. |
| `BOT_PROVIDER` | `openai` por defecto; `anthropic` o `google` para `agent-langgraph`. |
| `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` | Clave obligatoria del proveedor alternativo seleccionado. `agent-bot` sigue necesitando OpenAI aunque cambies el proveedor de LangGraph. |
| `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, `GOOGLE_GENERATIVE_AI_BASE_URL` | Endpoints accesibles desde los contenedores; vacío utiliza el proveedor. `localhost` apunta al contenedor, no al host. |
| `BOT_MODEL`, `AGENT_BOT_MODEL` | Modelo de LangGraph (vacío utiliza la especificación del proveedor) y del agente de ejemplo (por defecto `gpt-5.5`). |
| `BOT_RESPONSES_API`, `BOT_REASONING_EFFORT` | Responses API (`false` por defecto) y esfuerzo de razonamiento. Consulta las combinaciones admitidas en `docs/configuration.md`. |
| `CLAUDE_CODE_OAUTH_TOKEN` | Credencial alternativa avanzada que lee el servidor; no configura por sí sola un harness ni sustituye la clave del Bot LangGraph. |
| `COMPUTER_NETWORK` | Nombre real de la red de ordenadores, por defecto `openbot-coolify-computers`. Se usa tanto en `networks.default.name` como en el supervisor. |
| `COMPUTER_NAMESPACE` | Prefijo para los recursos dinámicos del supervisor, por defecto `openbot-coolify`. Usa un valor único por instalación. |
| `COMPUTER_RUNTIME` | Runtime Docker alternativo, por ejemplo `runsc`, solo si está instalado en el host. |
| `COMPUTER_MEMORY_BYTES` | Límite de RAM de cada ordenador dinámico; vacío usa el comportamiento del supervisor. |
| `COMPUTER_BROWSER_MODE` | `headed` por defecto; `headless` reduce necesidades gráficas. Se aplica también a los ordenadores dinámicos. |
| `COMPUTER_MAX_BROWSERS`, `COMPUTER_BROWSER_IDLE_MS`, `COMPUTER_MEMORY_HIGH_PERCENT`, `COMPUTER_TAB_IDLE_MS` | Ajustes del ordenador compartido, con los valores por defecto del programa al dejarlos vacíos. El supervisor actual no reenvía estos cuatro ajustes a los ordenadores dinámicos. |
| `SERVER_IMAGE`, `COMPUTER_IMAGE`, `SUPERVISOR_IMAGE`, `BOT_IMAGE`, `LANGGRAPH_IMAGE` | Referencias GHCR opcionales, por defecto `ghcr.io/brugiafredo/openbot-<servicio>:latest`. Admiten etiquetas `sha-<SHA completo>`; `COMPUTER_IMAGE` se comparte con el supervisor. |
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
- El Bot gestionado apunta directamente a `http://agent-langgraph:4201/ag-ui`.
  Su callback de herramientas es `http://server:3001/api/agent-tools/call`.
- `server` y `worker` arrancan sin perfiles; las migraciones bloquean su arranque si fallan.
  Se conserva `agent-bot` como ejemplo OpenAI, además del Bot LangGraph gestionado.
- Se omite `agent-harness`: su imagen depende de una selección del escritorio y puede
  quedar vacía. Tampoco se importan ficheros OAuth del escritorio ni sus montajes
  `.openbot` / `.langchain`. Para un harness propio hay que añadir una imagen concreta,
  sus credenciales y un endpoint interno; no basta con definir `PICKED_HARNESS_*`.
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
compartido. El supervisor crea **otros contenedores y volúmenes fuera del stack**,
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
dependencias y coherencia de la red. No ejecuta `docker compose config` y no acredita
un despliegue real, conectividad del proxy, licencia o credenciales de proveedores.
