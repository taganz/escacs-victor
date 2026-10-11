# Escacs Victor

Juega al ajedrez contra un bot en el navegador.

- Eliges color (blancas, negras o al azar).
- Reloj de 10 minutos por jugador más 5 segundos por jugada.
- Puedes rendirte o empezar una partida nueva.
- Al terminar, la partida se guarda en `games/partida_AAAA-MM-DD_HHMM.pgn`.

El bot es `bot/main.py` (ver [bot/README.md](bot/README.md)).

## Instalación en Windows

1. Instala [Python](https://www.python.org/downloads/) 3.10 o posterior.
   Marca «Add python.exe to PATH» en el instalador.
2. Descarga el repositorio (`git clone` o «Download ZIP»).
3. Copia `main.py` y `opening_book.json` en la carpeta `bot/`.
4. Haz doble clic en `run.bat`, o desde PowerShell escribe `.\run.bat`
   (en PowerShell hace falta el `.\` delante).
   La primera vez crea el entorno virtual e instala las dependencias.
   Después abre el navegador en http://localhost:8000.

Para pararlo, cierra la ventana negra o pulsa Ctrl+C en ella.

Si actualizas `requirements.txt`, borra la carpeta `.venv` y vuelve a ejecutar `run.bat`.

### Jugar desde otro equipo de casa

```
.\run.bat --host 0.0.0.0
```

Y abre `http://<IP del PC>:8000` desde el otro equipo. Puede que Windows
pregunte si permite el acceso en el cortafuegos.

## Instalación manual (Windows, Linux o Raspberry Pi)

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / Raspberry Pi
pip install -r requirements.txt
python -m server                # --host 0.0.0.0 --port 8000
```

Variables de entorno opcionales:

| Variable | Por defecto | Para qué |
|---|---|---|
| `ESCACS_BOT_FILE` | `bot/main.py` | Usar otro fichero de bot |
| `ESCACS_GAMES_DIR` | `games/` | Dónde se guardan los PGN |

## Cómo funciona

- **El servidor manda.** Valida las jugadas, lleva los relojes y decide cuándo
  termina la partida. La página solo dibuja lo que le envía el servidor por
  WebSocket (`/ws`).
- **Una partida a la vez.** Si recargas la página, sigues en la misma partida.
  Empezar una nueva durante una partida cuenta como abandono.
- **El bot corre en otro proceso**, así el servidor y los relojes siguen
  funcionando mientras piensa. Para cada jugada tiene
  `min(tiempo restante / 30 + 5, tiempo restante − 1)` segundos.
- **Final de partida:** jaque mate, rey ahogado, material insuficiente, triple
  repetición, regla de los 50 movimientos, tiempo agotado (tablas si el rival
  no tiene material para dar mate) y abandono.

| Fichero | Contenido |
|---|---|
| `server/game.py` | Reglas de la partida: turnos, final, resultado |
| `server/clock.py` | Reloj con incremento |
| `server/manager.py` | Partida en curso, turno del bot, caída de bandera |
| `server/bot_runner.py` | Ejecuta `bot/main.py` en otro proceso |
| `server/pgn_writer.py` | Genera el `.pgn` |
| `server/app.py` | Servidor web y WebSocket |
| `static/` | Página web |

## Tests

```
pip install -r requirements-dev.txt
pytest
```

## Créditos

Las piezas (`static/pieces.svg`) son de Colin M.L. Burnett (Wikimedia Commons),
con licencia CC BY-SA 3.0, en la versión adaptada por
[cm-chessboard](https://github.com/shaack/cm-chessboard).
