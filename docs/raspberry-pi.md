# Escacs Victor en una Raspberry Pi, accesible desde internet

Resultado final:

- En casa: `http://<nombre-de-la-pi>.local:8000`
- Desde cualquier sitio: `https://ajedrez.tudominio.com` (a través de Cloudflare Tunnel)

Cloudflare Tunnel no abre ningún puerto en el router: es la Pi la que se
conecta a Cloudflare. Tampoco hace falta IP fija ni configurar HTTPS.

Pensado para una Raspberry Pi 5 con Raspberry Pi OS de 64 bits.

## 1. Preparar la Pi

1. Graba la tarjeta con [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   - Sistema: **Raspberry Pi OS Lite (64-bit)**. No hace falta escritorio.
   - En la configuración (el engranaje o «Editar ajustes»):
     - nombre del equipo, por ejemplo `escacs`;
     - usuario y contraseña;
     - wifi, si no usas cable;
     - **activar SSH**.
2. Arranca la Pi y conéctate desde el PC (PowerShell):
   ```
   ssh <usuario>@escacs.local
   ```
3. Actualiza el sistema:
   ```
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y git
   ```

Recomendado: en el router, reserva una IP fija para la Pi (reserva DHCP). Así,
si `escacs.local` no funciona en algún dispositivo, puedes usar la IP.

## 2. Instalar el programa

```
git clone https://github.com/taganz/escacs-victor.git
cd escacs-victor
./scripts/install_pi.sh
```

Si el repositorio es privado, `git clone` pide usuario y contraseña. Como
contraseña usa un *token* de GitHub (Settings → Developer settings → Personal
access tokens) con permiso de lectura sobre este repositorio.

El script instala lo necesario, crea el servicio `escacs-victor` (arranca solo
al encender la Pi y se reinicia si falla) y al final muestra la dirección.

Prueba desde el PC o el móvil, conectado a la wifi de casa:
`http://escacs.local:8000`.

### Comandos útiles

| Para | Comando |
|---|---|
| Ver si funciona | `systemctl status escacs-victor` |
| Ver los registros en directo | `journalctl -u escacs-victor -f` |
| Reiniciar | `sudo systemctl restart escacs-victor` |
| Actualizar a la última versión | `./scripts/update_pi.sh` |
| Copiar las partidas al PC | `scp "<usuario>@escacs.local:escacs-victor/games/*.pgn" .` (desde PowerShell en el PC) |

Al actualizar o reiniciar se pierden las partidas que estén en curso. Las ya
terminadas están en `games/`.

## 3. Acceso desde internet con Cloudflare Tunnel

Necesitas que tu dominio esté gestionado en Cloudflare: los servidores DNS
del dominio tienen que ser los de Cloudflare. Si aún no lo está, en el panel
de Cloudflare usa «Add a domain» y sigue los pasos.

Los nombres de los menús de Cloudflare cambian a veces; si algo no cuadra,
busca «Tunnels» en el panel.

1. Entra en el panel de **Cloudflare Zero Trust** (desde el panel principal,
   «Zero Trust»). La primera vez te pide crear una organización. Elige el plan
   **Free**.
2. Ve a **Networks → Tunnels → Create a tunnel**.
3. Tipo **Cloudflared**. Ponle un nombre, por ejemplo `escacs`.
4. En «Install and run a connector», elige **Debian** y arquitectura
   **arm64**. Copia los comandos que aparecen y ejecútalos en la Pi por SSH.
   Instalan `cloudflared` y lo dejan como servicio con la clave del túnel.
   Cuando el conector aparezca como *Connected*, sigue.
5. En **Public hostname** (o «Published application routes»):
   - Subdomain: `ajedrez`, o el que quieras.
   - Domain: tu dominio.
   - Service: tipo **HTTP**, URL **`localhost:8000`**.
6. Guarda. En uno o dos minutos funciona `https://ajedrez.tudominio.com`.

Cloudflare pasa los WebSockets sin configurar nada, y la página usa `wss://`
automáticamente al abrirse por HTTPS.

### Opcional: limitar abusos

El programa ya limita las partidas simultáneas (4 en total y 2 por persona,
según su IP). Si alguien abusa, en el panel normal de Cloudflare, en tu
dominio → **Security → WAF → Rate limiting rules**, puedes crear una regla
gratuita, por ejemplo «más de 30 peticiones en 10 s desde la misma IP → bloquear».

## 4. Comprobar que todo funciona

- [ ] Desde el móvil **con datos móviles** (sin wifi) abre
      `https://ajedrez.tudominio.com` y juega una partida completa.
- [ ] Recarga la página a mitad de partida: tienes que volver a la misma partida.
- [ ] Al terminar, el botón **Descargar PGN** baja la partida, y en la Pi aparece
      en `~/escacs-victor/games/`.
- [ ] Reinicia la Pi (`sudo reboot`) y comprueba que la web vuelve sola, en casa y
      desde fuera.
- [ ] Mira en `journalctl -u escacs-victor` que no haya errores.

## Problemas frecuentes

| Síntoma | Qué mirar |
|---|---|
| `escacs.local` no responde | Usa la IP de la Pi. Algunos Android no resuelven `.local`. |
| En casa funciona y fuera no | Panel de Cloudflare: el túnel tiene que estar *Healthy* y el servicio debe ser `http://localhost:8000`. En la Pi: `systemctl status cloudflared`. |
| La página carga pero pone «Sin conexión con el servidor» | El WebSocket no llega. Revisa que el *hostname* apunte a `localhost:8000` y no a otro puerto. |
| «El servidor está ocupado» | Hay 4 partidas en curso. Se liberan al terminar (como mucho cuando se acaba el reloj). |
| El bot falla | `journalctl -u escacs-victor -n 100` muestra el error de `bot/vicescacs.py`. |

## Cómo funciona por dentro

- El servicio `escacs-victor` ejecuta `python -m server --host 0.0.0.0 --port 8000`.
  `0.0.0.0` hace que se pueda entrar desde la red de casa.
- `cloudflared` recibe las visitas de internet y las pasa a `localhost:8000`.
- Cada navegador tiene su propia partida y su propio proceso de bot. Una partida
  abandonada termina sola cuando se le acaba el reloj al jugador.
