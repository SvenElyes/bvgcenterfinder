"""Flask web server for the BVG meeting-point finder."""
from __future__ import annotations

import io
import json
from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from staticmap import StaticMap, CircleMarker, Line

from api import resolve_stop, score_candidates
from strategies import REGISTRY

app = Flask(__name__)


def _serialize_results(ranked, starts, top):
    results = []
    for s in ranked[:top]:
        results.append({
            "name": s.candidate.name,
            "id": s.candidate.id,
            "lat": s.candidate.lat,
            "lon": s.candidate.lon,
            "max_min": round(s.max_min, 1),
            "sum_min": round(s.sum_min, 1),
            "per_person_min": [round(m, 1) for m in s.per_person_min],
        })
    return results


@app.get("/")
def index():
    strategies = {name: mod.DESCRIPTION for name, mod in sorted(REGISTRY.items())}
    return render_template("index.html", strategies=strategies)


@app.post("/api/find")
def api_find():
    body = request.get_json(force=True)
    queries: list[str] = body.get("starts", [])
    strategy_name: str = body.get("strategy", "union")
    when: str | None = body.get("when") or None
    top: int = int(body.get("top", 3))
    radius: int = int(body.get("radius", 2000))
    candidates_n: int = int(body.get("candidates", 30))

    if len(queries) < 2:
        return jsonify(error="Need at least 2 start locations."), 400
    if strategy_name not in REGISTRY:
        return jsonify(error=f"Unknown strategy: {strategy_name!r}"), 400

    try:
        starts = [resolve_stop(q) for q in queries]
    except ValueError as e:
        return jsonify(error=str(e)), 400

    strategy = REGISTRY[strategy_name]
    cands = strategy.get_candidates(starts, radius=radius, results=candidates_n)
    start_ids = {s.id for s in starts}
    cands = [c for c in cands if c.id not in start_ids]

    ranked = score_candidates(starts, cands, when)
    if not ranked:
        return jsonify(error="No reachable candidate stops found."), 404

    starts_info = [{"name": s.name, "id": s.id, "lat": s.lat, "lon": s.lon} for s in starts]
    return jsonify(results=_serialize_results(ranked, starts, top), starts=starts_info)


@app.get("/api/map")
def api_map():
    """Return a PNG map with start markers (blue) and meeting stop (red) connected by lines."""
    try:
        meet_lat = float(request.args["meet_lat"])
        meet_lon = float(request.args["meet_lon"])
        start_lats = [float(x) for x in request.args.getlist("slat")]
        start_lons = [float(x) for x in request.args.getlist("slon")]
    except (KeyError, ValueError):
        return jsonify(error="Missing or invalid params"), 400

    m = StaticMap(700, 500, padding_x=40, padding_y=40)

    for slat, slon in zip(start_lats, start_lons):
        m.add_line(Line([(slon, slat), (meet_lon, meet_lat)], "#4488cc", 2))

    for slat, slon in zip(start_lats, start_lons):
        m.add_marker(CircleMarker((slon, slat), "#0057a8", 12))

    m.add_marker(CircleMarker((meet_lon, meet_lat), "#cc0000", 16))

    image = m.render()
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.read(), mimetype="image/png")


@app.post("/api/find/all")
def api_find_all():
    """SSE endpoint: runs all strategies sequentially, streaming progress events."""
    body = request.get_json(force=True)
    queries: list[str] = body.get("starts", [])
    when: str | None = body.get("when") or None
    top: int = int(body.get("top", 3))
    radius: int = int(body.get("radius", 2000))
    candidates_n: int = int(body.get("candidates", 30))

    if len(queries) < 2:
        return jsonify(error="Need at least 2 start locations."), 400

    def generate():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        try:
            starts = [resolve_stop(q) for q in queries]
        except ValueError as e:
            yield sse("error", {"message": str(e)})
            return

        starts_info = [{"name": s.name, "id": s.id, "lat": s.lat, "lon": s.lon} for s in starts]
        strategy_names = sorted(REGISTRY.keys())
        total = len(strategy_names)

        yield sse("start", {"total": total, "starts": starts_info})

        for i, name in enumerate(strategy_names):
            yield sse("strategy_start", {"index": i, "name": name, "description": REGISTRY[name].DESCRIPTION})

            try:
                strategy = REGISTRY[name]
                cands = strategy.get_candidates(starts, radius=radius, results=candidates_n)
                start_ids = {s.id for s in starts}
                cands = [c for c in cands if c.id not in start_ids]
                ranked = score_candidates(starts, cands, when)

                if ranked:
                    results = _serialize_results(ranked, starts, top)
                    yield sse("strategy_done", {"index": i, "name": name, "results": results})
                else:
                    yield sse("strategy_done", {"index": i, "name": name, "results": [], "warning": "No reachable stops"})
            except Exception as e:
                yield sse("strategy_done", {"index": i, "name": name, "results": [], "error": str(e)})

        yield sse("complete", {"total": total})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
