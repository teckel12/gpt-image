import logging

from backend.app import create_app

logging.basicConfig(level=logging.INFO)
create_app().run(host="127.0.0.1", port=5050, debug=True)
