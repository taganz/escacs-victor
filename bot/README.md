# Bot

Pon aquí `vicescacs.py` y `opening_book.json`.

El servidor solo usa esta función de `vicescacs.py`:

```python
def choose_move(board: chess.Board, time_limit: float) -> chess.Move:
```

- `board` es una copia del tablero, con todas las jugadas de la partida.
- `time_limit` son los segundos que el bot puede pensar en esta jugada.
  Si se pasa, el tiempo sale de su reloj y puede perder por tiempo.
- Tiene que devolver una jugada legal. Si devuelve una ilegal o lanza una
  excepción, el servidor juega una jugada al azar y lo muestra en pantalla.

El fichero tiene que poder importarse sin efectos: el código de prueba por
consola debe ir dentro de `if __name__ == "__main__":`.

Mientras `vicescacs.py` no exista o no defina `choose_move`, el servidor usa un bot
provisional que juega al azar y lo avisa en la página.

El bot se ejecuta en un proceso aparte con este directorio como directorio de
trabajo, así que `open("opening_book.json")` funciona.

**No subas tokens ni contraseñas** en `vicescacs.py`.
