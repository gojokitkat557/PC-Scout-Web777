# PC Scout Web Auto

Página estática + datos separados + actualización mediante GitHub Actions.

- `index.html`: página.
- `pcs.json`: lista actual.
- `history.json`: historial de precio/estado.
- `sources.json`: URLs monitorizadas.
- `scripts/update_wallapop.py`: actualizador.
- `.github/workflows/update.yml`: ejecución cada 2 horas.

Importante: Wallapop puede bloquear o cambiar sus páginas. El script conserva el último dato válido si recibe 403/429/5xx; no borra un PC por un bloqueo temporal.
