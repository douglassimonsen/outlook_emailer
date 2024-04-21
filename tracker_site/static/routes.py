from typing import Optional
from application import application, cache
import flask
import pandas
import io
import time
import os
import json
import psycopg2
from psycopg2.extensions import connection

def get_conn() -> connection:
    creds = json.loads(os.environ["EMAIL_DB_CREDS"])
    return psycopg2.connect(**creds)


@application.route('/logo.png')
def render_real_logo():
    @cache.cached()
    def get_data():
        with open('static/logo.png', 'rb') as f:
            f = io.BytesIO(f.read())
            f.seek(0)
        return f

    return flask.send_file(get_data(), mimetype='image/png')


@application.route('/logo_<info>.png')
def render_logo(info):
    def get_data():
        with open('page_backends/cta_logo/logo_large.png', 'rb') as f:
            f = io.BytesIO(f.read())
            f.seek(0)
        for b in f:
            yield b
            time.sleep(.1)
            update_info()

    def update_info():
        time_ended = pandas.Timestamp(time.time(), unit='s', tz='America/Chicago')
        query = '''
        update public.email_tracking set time_ended = %(time_ended)s
        where recipient = %(recipient)s
        and subject = %(subject)s
        and ip_addr = %(ip_addr)s
        and time_received = %(time_received)s
        '''
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(query, {
                "recipient": name,
                "subject": subject,
                'ip_addr': ip.split(', ', 1)[0],
                'time_received': time_received,
                'time_ended': time_ended,
            })
            conn.commit()

    def save_info():
        query = '''
        insert into public.email_tracking (recipient, subject, ip_addr, time_received)
        values (%(recipient)s, %(subject)s, %(ip_addr)s, %(time_received)s)
        '''
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(query, {
                "recipient": name,
                "subject": subject,
                'ip_addr': ip.split(', ', 1)[0],
                'time_received': time_received,
            })
            conn.commit()

    time_received = pandas.Timestamp(time.time(), unit='s', tz='America/Chicago')
    info = info.split('_')
    len_info = len(info)
    name: Optional[str] = info[0] if len_info >= 1 else None
    subject: Optional[str] = info[1] if len_info >= 2 else None
    if flask.request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        ip: str = flask.request.environ['REMOTE_ADDR']
    else:
        ip: str = flask.request.environ.get('HTTP_X_FORWARDED_FOR', flask.request.remote_addr or '')

    save_info()
    resp = flask.Response(flask.stream_with_context(get_data()), mimetype='image/png')
    return resp
