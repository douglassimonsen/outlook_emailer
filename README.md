A tool for easily sending emails via exchangelib. Includes logging and automatic tracker. To use yourself, you must fill in DEFINES.yaml with the appropriate values.

The program contains two functions designed for public consumption:
* main.send_email
* main.get_exchangelib_account

## main.send_email
This function is the main function of the program. It is designed to provide a simple API for non-developers to send emails automatically. It implements all basic email functionality, as well as:
* Importance levels
* Image based tracking to tell who has opened emails, automatically. (Requires you set up the tracker_site)
* Handles attachments, whether passed as filepaths or io.BytesIO buffers. 
* Optional "already sent" checking, in case the automatic email is part of a larger Cron or Airflow, making it idempotent.
* Built-in logging for failures and successes, making it easier to generate reports about your automatic emails (requires seperate Postgres DB)

```python
send_email(
    account_email='mhamilton',
    subject='Just a Test',
    html_body='''
        <p>hi</p>
        <p style="background-color='blue'">Goodbye</p>
    ''',
    tracker=True,
    importance='high',
    to_list=['mhamilton'],
    defines='DEFINES.yaml'
)
```

## main.get_exchangelib_account
This function provides a much simpler (and less flexible) way of accessing your exchangelib account than the API exchangelib provides. It's designed to autodiscover your email server and log into your inbox or an inbox you have access to.

```python
defines = {
    'DEFAULT_SITE': '@personal_site.com',
    'DATABASE': {
        'host': 'postgres.heroku.com',
        'port': '5432',
        'database': 'db',
        'user': 'user',
        'password': 'pass',
    },
}
get_exchangelib_account('mwhamilton', 'group_email', 'password', defines)
```

## DEFINES example
```yaml
DEFAULT_SITE: gmail.com
EMAIL_PASSWORD: not_really_a_password
SEND_ATTEMPTS: 5
SLEEP_BETWEEN_SEND_ATTEMPTS: 1
DATABASE:
  host: postgres.heroku.com
  port: 5432
  database: 'db'
  username: db_user
  password: yet_another_fake_password
TRACKER:
  COVER_IMAGE_URL: site.heroku.com/logo.png
  TRACKER_BASE_URL: site.heroku.com
```

## Setting Up Logging
To log email failures and successes, first start/log into a postgres instance. Then run the SQL in `generate_logging_tables.sql`.
Then create a user for the program to use and give that user permission to insert and select on the tables.
Add the host, port, database, user and password into your `DEFINES.yaml` file.
