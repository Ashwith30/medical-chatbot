"""
Medical ChatBot — Flask Application
Serves the chat UI and exposes the hybrid medical search API.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import traceback

# Load .env before importing search engine
load_dotenv()

from engine.search import hybrid_medical_search

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")
CORS(app)

DISCLAIMER = (
    "⚠️ This information is for educational purposes only and does not constitute "
    "medical advice. Always consult a qualified healthcare professional."
)


# ──────────────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────────────

@app.route("/")
def home():
    """Serve the main chatbot UI."""
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search_api():
    """
    POST /search
    Body: { "query": "<user question>" }

    Response shapes:

    1. Rejected (non-medical):
       { status: "rejected", message: "..." }

    2. Codes + LLM enrichment (local DB hit with context):
       { status: "success", source: "local+llm",
         codes: [...], enrichment: "...", warning: "..." (if any), disclaimer: "..." }

    3. LLM explanation (+ optional related codes):
       { status: "success", source: "llm",
         explanation: "...", codes: [...], warning: "..." (if any), disclaimer: "..." }

    4. Local DB only (LLM unavailable):
       { status: "success", source: "local",
         codes: [...], warning: "..." (if any), disclaimer: "..." }

    5. Empty:
       { status: "empty", message: "..." }

    6. Error:
       { status: "error", message: "Internal server error" }
    """
    try:
        body = request.get_json(silent=True)

        if not body:
            return jsonify({"status": "error", "message": "No JSON body received"}), 400

        query = body.get("query", "").strip()

        if not query:
            return jsonify({"status": "empty", "message": "Query is empty."}), 400

        if len(query) > 500:
            return jsonify({"status": "error", "message": "Query too long (max 500 chars)."}), 400

        # ── Run hybrid search ───────────────────────────────
        result = hybrid_medical_search(query)
        source = result.get("source", "empty")

        # ── Rejected (non-medical) ──────────────────────────
        if source == "rejected":
            return jsonify({
                "status":  "rejected",
                "message": result.get("data", "I can only answer medical questions."),
            }), 200

        # ── Codes + LLM enrichment ──────────────────────────
        if source == "local+llm":
            response = {
                "status":      "success",
                "source":      "local+llm",
                "codes":       result.get("codes", []),
                "enrichment":  result.get("enrichment", result.get("data", "")),  # Fallback to data if enrichment empty
                "disclaimer":  DISCLAIMER,
            }
            if "warning" in result:
                response["warning"] = result["warning"]
            return jsonify(response), 200

        # ── Pure LLM explanation (+ optional codes) ─────────
        if source == "llm":
            # Use either 'data' or 'explanation' field
            explanation_text = result.get("data") or result.get("enrichment", "")
            response = {
                "status":      "success",
                "source":      "llm",
                "data":        explanation_text,  # Frontend expects 'data' field
                "codes":       result.get("codes", []),   # may be empty
                "disclaimer":  DISCLAIMER,
            }
            if "warning" in result:
                response["warning"] = result["warning"]
            return jsonify(response), 200

        # ── Local DB only (LLM failed) ──────────────────────
        if source == "local":
            response = {
                "status":     "success",
                "source":     "local",
                "codes":      result.get("codes", []),
                "disclaimer": DISCLAIMER,
            }
            
            # If we have data (e.g., from project.json), return it as enrichment
            if result.get("data"):
                response["enrichment"] = result.get("data")
            
            if "warning" in result:
                response["warning"] = result["warning"]
            return jsonify(response), 200

        # ── Empty / no results ──────────────────────────────
        return jsonify({
            "status":  "empty",
            "message": result.get("data", "No results found for your query."),
        }), 200

    except Exception as e:
        print("[ERROR] /search exception:")
        traceback.print_exc()
        return jsonify({
            "status":  "error",
            "message": "Internal server error. Please try again.",
        }), 500


@app.route("/health")
def health_check():
    """Lightweight health probe."""
    return jsonify({
        "status":  "healthy",
        "service": "Medical ChatBot",
        "version": "2.0",
    }), 200


# ──────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    port  = int(os.getenv("PORT", 5020))

    print(f"🏥  Medical ChatBot starting on port {port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=debug)