"""Development entry point for the Typing Behaviour Analyzer.

The server runs as a single process: Flask's automatic reloader is disabled so
that Ctrl+C in the starting terminal stops the server cleanly and never leaves
a reloader child holding port 5000. Debug mode stays enabled for the Werkzeug
debugger.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
