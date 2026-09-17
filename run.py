from app import create_app
import os

app = create_app()


if __name__ == "__main__":
    debug = os.environ.get("CYBERREADY_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(debug=debug)
