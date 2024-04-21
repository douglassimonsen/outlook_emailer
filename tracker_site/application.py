import flask
from flask_caching import Cache
application = flask.Flask(__name__)
cache = Cache(application, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 100, 'CACHE_THRESHOLD': 100000, })
from static import routes  # noqa

if __name__ == "__main__":
    application.run()
