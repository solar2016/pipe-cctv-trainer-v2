from __future__ import annotations

from flask import Flask, jsonify, render_template

from config import PORT, ensure_dirs

app = Flask(__name__, static_folder="static", template_folder="templates")
ensure_dirs()

# Register route blueprints
from routes.samples import bp as samples_bp
from routes.predict import bp as predict_bp
from routes.anchors import bp as anchors_bp
from routes.evaluation import bp as evaluation_bp
from routes.prompts import bp as prompts_bp
from routes.standards import bp as standards_bp
from routes.settings import bp as settings_bp
from routes.video import bp as video_bp
from routes.report import bp as report_bp
from routes.kupas import bp as kupas_bp

app.register_blueprint(samples_bp)
app.register_blueprint(predict_bp)
app.register_blueprint(anchors_bp)
app.register_blueprint(evaluation_bp)
app.register_blueprint(prompts_bp)
app.register_blueprint(standards_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(video_bp)
app.register_blueprint(report_bp)
app.register_blueprint(kupas_bp)


@app.get("/")
def index():
    return render_template("workspace.html")


@app.get("/standards")
def standards_page():
    return render_template("standards.html")


@app.get("/evaluation")
def evaluation_page():
    return render_template("evaluation.html")


@app.get("/settings")
def settings_page():
    return render_template("settings.html")


@app.get("/prompts")
def prompts_page():
    return render_template("prompts.html")


@app.get("/api/defects")
def api_defects():
    from core.taxonomy import all_codes, get_defects, get_category_map
    defects = get_defects()
    category_map = get_category_map()
    codes = []
    for code in all_codes():
        item = defects.get(code, {})
        codes.append({
            "code": code,
            "name": item.get("name", code),
            "category": item.get("category", ""),
            "category_key": category_map.get(code, "other"),
        })
    return jsonify({"codes": codes})


@app.get("/health")
def health():
    from services.sample_service import load_samples
    return jsonify({"ok": True, "samples": len(load_samples())})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=os.getenv("FLASK_DEBUG", "0") == "1")
