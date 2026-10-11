# Bot

El bot es `vicescacs.py`. Usa el libro de aperturas `opening_book.json` mientras
la posición esté en él, y después busca con minimax y poda alfa-beta a
profundidad 4.

El servidor solo usa esta función de `vicescacs.py`:

```python
def choose_move(board: chess.Board, time_limit: float) -> chess.Move:
```

- `board` es una copia del tablero, con todas las jugadas de la partida
  (si la partida empezó desde un FEN, las jugadas desde esa posición).
- `time_limit` son los segundos que el bot puede pensar en esta jugada.
  Si se pasa, el tiempo sale de su reloj y puede perder por tiempo.
  Ahora mismo `vicescacs.py` no lo usa: busca siempre a profundidad 4,
  tarde lo que tarde.
- Tiene que devolver una jugada legal. Si devuelve una ilegal o lanza una
  excepción, el servidor juega una jugada al azar y lo muestra en pantalla.

El fichero tiene que poder importarse sin efectos: el código de prueba por
consola debe ir dentro de `if __name__ == "__main__":`.

Mientras `vicescacs.py` no exista, tenga un error de sintaxis o no defina
`choose_move`, el servidor usa un bot provisional que juega al azar y lo avisa
en la página. Ojo: un `if __name__ == "__main__":` con todo el contenido
comentado es un error de sintaxis; pon `pass` dentro.

Si añades un `import` de una librería que no sea `chess`, añádela también a
`requirements.txt`; si no, el bot falla al cargarse.

El bot se ejecuta en un proceso aparte con este directorio como directorio de
trabajo, así que `open("opening_book.json")` funciona.

**No subas tokens ni contraseñas** en `vicescacs.py`.
