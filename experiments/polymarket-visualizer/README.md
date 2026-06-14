# Polymarket Scanner + p5.js Weather Visualizer

Read-only experiment for scanning Polymarket public markets and visualizing market probability movement as generative art.

## Files

- `polymarket_scanner.py` — fetches public Gamma/CLOB/Data API data, computes simple signals, writes snapshot files.
- `index.html` — p5.js visualizer. Loads `data/polymarket_snapshot.json` and `data/polymarket_history.json` when served over HTTP; falls back to demo data.
- `data/` — output directory for generated snapshots.

## Run the scanner

From this folder:

```bash
python3 polymarket_scanner.py --limit 80 --history-limit 25 --interval 1d --fidelity 96
```

Optional slower order-book/spread fetch:

```bash
python3 polymarket_scanner.py --limit 80 --history-limit 25 --fetch-books
```

The scanner first tries CLOB price history, then falls back to recent Data API trades when CLOB history is empty.

Outputs:

```text
data/polymarket_snapshot.json
data/polymarket_markets.csv
data/polymarket_history.json
```

## Open the visualizer

Because browsers block some local file fetching, serve the folder over HTTP:

```bash
python3 -m http.server 8123
```

Then open:

```text
http://localhost:8123/index.html
```

Controls:

- `Space` pause/resume
- `H` toggle HUD
- `R` reshuffle seed/layout
- `S` save PNG
- Click an orb to pin it
- Hover an orb for details

## Notes

This is read-only and not financial advice. The signals are exploratory, not trade recommendations. Polymarket prices can be wrong, illiquid, delayed, or resolved in surprising ways.
