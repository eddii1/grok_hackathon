# Skytrace website and dashboard

Standalone static landing page with a bundled interactive dashboard. No build or dependency installation is required to run the site.

From this directory:

```sh
python3 -m http.server 4173 --bind 127.0.0.1
```

Open http://127.0.0.1:4173/. All landing-page demo links open `dashboard/index.html`.

The dashboard is copied from the existing Skytrace local export, including its fonts, inventory tools and demo data. It is an interactive prototype: aircraft telemetry, findings, maps and copilot responses are illustrative. It does not connect to aircraft or call an AI service. Demo state persists in the browser.

The earlier mission-flow simulator remains available at `simulator.html`. Its cancellation regression script is optional and requires an externally installed `puppeteer-core` and Google Chrome:

```sh
node check-simulator.js http://127.0.0.1:4173/simulator.html
```

Set `NODE_PATH` to the external dependency directory if needed, and `CHROME` if Chrome is installed at a different path.

Local visual-review evidence is ignored under `review-evidence/`. Visual fidelity to the reference is still under review; measured animation improvements do not establish exact visual parity. Newsletter subscriptions and real device integrations are not configured.
