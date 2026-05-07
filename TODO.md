# BVG Web UI — TODO
<!-- Ranked by effort / Claude Code token cost (cheapest → most expensive) -->

- [x] Install Flask and staticmap dependencies  <!-- effort: trivial — one shell command -->
- [x] Create `app.py` Flask server with `GET /` route serving index.html  <!-- effort: low — ~30 lines of boilerplate -->
- [x] Add `POST /api/find` endpoint: resolves stops, runs scoring, returns top-3 JSON  <!-- effort: medium — glue code wrapping existing bvg.py logic -->
- [x] Create `templates/index.html` with UI (address inputs, + button, strategy selector, calculate button)  <!-- effort: medium — scales with how polished the UI needs to be -->
- [x] Wire up frontend JS: call `/api/find` on button click, render results table, fetch and display map image  <!-- effort: medium-high — fetch, DOM manipulation, error handling, loading states -->
- [x] Add `GET /api/map` endpoint: generates static PNG map with markers + lines via staticmap  <!-- effort: high — unfamiliar API, marker/line syntax, image serving -->
- [ ] Smoke-test the full flow end-to-end in the browser  <!-- effort: highest — running server + real API calls + visual checks + fix cycles -->
