import exchangelib
import datetime
import os
import time
import psutil
import pandas
import yaml
import io
import sys
import json
import psycopg2
from typing import Iterable, Union, Optional

AttachmentListType = Optional[Iterable[Union[str, dict]]]
RecipientListType = Union[Iterable[str], str]


def get_logging_conn(host: str, port: Union[str, int], database: str, username: str, password: str):
    return psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password,
    )


def get_exchangelib_account(access_account: str=None, inbox_account: Optional[str]=None, password: str=None, defines: dict={}):
    """
    :param access_account: the name of the email addr you are accessing from
    :inbox_account: the name of the email addr that will appear in the from. If None, then it defaults to access_account
    :password: the password for the access_account
    """

    inbox_account = inbox_account or access_account
    if "@" not in inbox_account:
        inbox_account = inbox_account + defines['DEFAULT_SITE']
    if "@" not in access_account:
        access_account = access_account + defines['DEFAULT_SITE']
    if password is None:
        raise ValueError("The email needs a password to connect to the server")

    credentials = exchangelib.Credentials(username=access_account, password=password)
    config = exchangelib.Configuration(
        retry_policy=exchangelib.FaultTolerance(max_wait=120),
        credentials=credentials,
        service_endpoint="https://autodiscover-s.outlook.com/Autodiscover/Autodiscover.xml",
        auth_type="basic",
    )
    try:
        return exchangelib.Account(
            primary_smtp_address=inbox_account,
            credentials=credentials,
            autodiscover=True,
            access_type=exchangelib.DELEGATE,
            config=config,
        )
    except (exchangelib.errors.AutoDiscoverError, exchangelib.errors.AutoDiscoverFailed):
        _log_email_failure(inbox_account, access_account, password, defines['DATABASE'])
        raise exchangelib.errors.AutoDiscoverError("Generally, this error occurs when your credentials are out of date")
    except AttributeError:
        raise AttributeError("It seems like the username is wrong")


def _send(access_account: str, sending_email: str, password: str, subject: str, max_send_interval: Optional[int], body: str, recipients: dict, importance: str, attachments: AttachmentListType, defines: dict):
    def check_already_sent(account, interval, subject):
        tz = exchangelib.EWSTimeZone.localzone()
        if interval == "daily":
            threshold_dt = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        elif interval == "hourly":
            threshold_dt = datetime.datetime.today().replace(minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"The '{interval}' interval has not been implemented yet")
        threshold_dt = tz.localize(exchangelib.EWSDateTime.fromtimestamp(tz.localize(threshold_dt).timestamp()))
        cnt = account.sent.filter(datetime_received__gte=threshold_dt, subject=subject).count()
        return cnt > 0

    account = get_exchangelib_account(access_account=access_account, inbox_account=sending_email, password=password, defines=defines)

    if max_send_interval is not None:
        # This is not perfect. If you try to send an email multiple times in a very quick succession (like <2 seconds between), you can still get duplicates. This is an
        # exchangelib/you problem, not a this package problem. Also, if you delete the email from your sent folder this function won't find it.
        if check_already_sent(account, max_send_interval, subject):
            return

    for _ in range(defines['SEND_ATTEMPTS']):
        try:
            email = exchangelib.Message(
                account=account,
                folder=account.sent,
                subject=subject,
                body=body,
                to_recipients=recipients["to"],
                cc_recipients=recipients["cc"],
                bcc_recipients=recipients["bcc"],
                importance=importance,
            )
            break
        except exchangelib.errors.ErrorNoRespondingCASInDestinationSite:  # occurs when the exchangelib server cannot get the account.sent folder
            print("failed to access remote exchangelib server")
            time.sleep(defines['SLEEP_BETWEEN_SEND_ATTEMPTS'])
    else:
        raise LookupError("We could not access the server to get the sent folder")

    for attachment in attachments:
        email.attach(exchangelib.FileAttachment(name=attachment["name"], content=attachment["buffer"].read()))

    for i in range(defines['SEND_ATTEMPTS']):
        try:
            email.send_and_save()
            break
        except:
            print(f"Attempt {i} failed to send to server.")
            time.sleep(defines['SLEEP_BETWEEN_SEND_ATTEMPTS'])
    else:
        raise ValueError("Couldn't send email to server")


def process_email_addresses(account_email: str, sending_email: Optional[str], to_list: RecipientListType, cc_list: Optional[RecipientListType], bcc_list: Optional[RecipientListType]):

    if not to_list:
        raise ValueError("The email needs to be sent to someone. Please add a list to to_list.")

    sending_email = sending_email or account_email
    if "@" not in account_email:
        account_email += "@transitchicago.com"
    if "@" not in sending_email:
        sending_email += "@transitchicago.com"

    recipients = {
        "to": to_list,
        "cc": cc_list or [],
        "bcc": bcc_list or [],
    }
    for lst_name, lst in recipients.items():
        if isinstance(lst, str):
            recipients[lst_name] = [lst]
        for i in range(len(recipients[lst_name] or [])):
            if "@" not in recipients[lst_name][i]:
                recipients[lst_name][i] += "@transitchicago.com"

    return account_email, sending_email, recipients


def process_email_body(body: str, html_body: str, tracker: bool, subject: str, recipients: Iterable[str], defines: dict):
    if tracker is not False:
        text = html_body or f'<pre style=\'font-size:14.667px;font-family:"Calibri"\'>{body or ""}</pre>'
        tracker_url = _add_tracker(subject, recipients, defines)
        html_body = f"""{text}
        <table border="0" cellpadding="0" cellspacing="0" style="width:226.0pt; margin-left:4.65pt; border-collapse:collapse">
          <tr>
            <td rowspan=3><img src="{defines['TRACKER']['COVER_IMAGE_URL']}" alt="CTA logo" width="50" height="50"></img><img src="{tracker_url}" alt="CTA logo" width="1" height="1"></img></td>
            <td>Performance Management</td>
          </tr>
          <tr>
            <td>Automatic Email</td>
          </tr>
          <tr>
            <td></td>
          </tr>
        </table>
        """
    if html_body is not None:
        body = exchangelib.HTMLBody(html_body)

    return body


def process_attachments(attachments: AttachmentListType):
    attachments = attachments or []
    if not isinstance(attachments, list):
        attachments = [attachments]
    for i, attachment in enumerate(attachments):
        if isinstance(attachment, dict):
            attachment["buffer"].seek(0)
        if isinstance(attachment, str):
            with open(attachment, "rb") as input_file:
                f = io.BytesIO(input_file.read())
            f.seek(0)  # important, otherwise, exchangelib will start reading from the end of the file and think it's empty
            attachments[i] = {"name": os.path.basename(attachment), "buffer": f}
    return attachments  # you might think you can just remove the return because it's being edited in place. The case were attachments is None causes this to fail


def process_defines(defines: Union[dict, str]):
    if isinstance(defines, str):
        with open(defines, 'r') as f:
            if defines.endswith(".yaml"):
                return yaml.load(f, Loader=yaml.FullLoader)
            if defines.endswith(".json"):
                return json.load(f)
    if isinstance(defines, dict):
        return defines
    raise ValueError("The defines should either be a dictionary, or a path to a JSON or YAML")


def _log_email_success(subject: str, sending_email: str, recipients: Iterable[str], database: dict):
    process = psutil.Process(os.getpid())
    process_parents = []
    while process is not None:
        process_parents.append(process.name())
        process = process.parent()
    with get_logging_conn(**database) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """insert into public.email_successes (subject, sender, time_sent, to_list, filepath, processes)
            values (%(subject)s, %(sender)s, %(time_sent)s, %(to_list)s, %(filepath)s, %(processes)s)""",
            {
                "subject": subject,
                "sender": sending_email,
                "time_sent": datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
                "to_list": json.dumps(recipients),
                "filepath": os.path.abspath(sys.argv[0]),
                "processes": json.dumps(process_parents),
            },
        )
        conn.commit()


def _log_email_failure(account_email: str, sending_email: str, password: str, database: dict):
    query = """
    insert into public.email_failures (account_email, sending_email, password, filepath)
    values (%(account_email)s, %(sending_email)s, %(password)s, %(filepath)s)
    """
    import inspect

    for frame in inspect.stack():
        filepath = inspect.getmodule(frame[0]).__file__
        if "pm_utilities" not in filepath:  # we want the first frame that calls pm_utilities
            break
    with get_logging_conn(**database) as conn:
        cursor = conn.cursor()
        cursor.execute(query, {"account_email": account_email, "sending_email": sending_email, "password": password, "filepath": filepath})
        conn.commit()


def _add_tracker(subject: str, recipients: dict, defines):
    tmp_recipients = ";".join(sorted(set(x.split("@", 1)[0] for x in recipients["to"] + recipients["cc"] + recipients["bcc"])))

    subject_query = """
    select index from public.email_subject_detail where subject = %(subject)s
    limit 1
    """
    max_subject = """
    select max(index) as mx from public.email_subject_detail
    """
    insert_subject = """
    insert into public.email_subject_detail (index, subject) values (%(index)s, %(subject)s)
    """

    recipient_query = """
    select index from public.email_recipients_detail where recipients = %(recipients)s
    limit 1
    """
    max_recipient = """
    select max(index) as mx from public.email_recipients_detail
    """
    insert_recipient = """
    insert into public.email_recipients_detail (index, recipients) values (%(index)s, %(recipients)s)
    """
    with get_logging_conn(**defines['DATABASE']) as conn:
        subject_index = pandas.read_sql(subject_query, conn, params={"subject": subject})
        if subject_index.shape[0] == 0:
            subject_index_val = int(pandas.read_sql(max_subject, conn)["mx"].iloc[0] or 0) + 1
            cursor = conn.cursor()
            cursor.execute(insert_subject, {"index": subject_index_val, "subject": subject})
            conn.commit()
        else:
            subject_index_val = subject_index["index"].iloc[0]

        recipient_index = pandas.read_sql(recipient_query, conn, params={"recipients": tmp_recipients})
        if recipient_index.shape[0] == 0:
            recipient_index_val = int(pandas.read_sql(max_recipient, conn)["mx"].iloc[0] or 0) + 1
            cursor = conn.cursor()
            cursor.execute(
                insert_recipient, {"index": recipient_index_val, "recipients": tmp_recipients},
            )
            conn.commit()
        else:
            recipient_index_val = recipient_index["index"].iloc[0]
    return f"{defines['TRACKER']['TRACKER_BASE_URL']}/logo_{recipient_index_val}_{subject_index_val}.png"


def main(
    account_email: str=None,
    sending_email: Optional[str]=None,
    password: str=None,
    to_list: RecipientListType=None,
    cc_list: Optional[RecipientListType]=None,
    bcc_list: Optional[RecipientListType]=None,
    subject: Optional[str]=None,
    body: Optional[str]=None,
    html_body: Optional[str]=None,
    attachments: AttachmentListType=None,
    importance: str="Normal",
    tracker: bool=False,
    max_send_interval: Optional[str]=None,
    defines: Union[dict, str]={},
):
    """
    :param account_email: The account to access outlook
    :param sending_email: The account to send the email from. Defaults to account_email
    :param password: The password for the account_email. If None, pm_utilities will try to automatically determine it.
    :param to_list: A list of email addresses. If the email has no '@', will append '@transitchicago.com'
    :param cc_list: A list of email addresses. If the email has no '@', will append '@transitchicago.com'
    :param bcc_list: A list of email addresses. If the email has no '@', will append '@transitchicago.com'
    :param subject: A string representing the subject
    :param body: A string of raw text
    :param html_body: A html formatted string
    :param attachments: A list of strings representing the path to a file or a dictionary like {'name': 'test.csv', 'buffer': <io.BytesIO()>}
    :param importance: 'Low', 'Normal', and 'High'.
    :param tracker: If true, generates a CTA logo that will record IP addresses looking at the email (only on CTA network)
    :param defines: A dictionary of values to specify global values
    """
    defines = process_defines(defines)
    importance = importance.capitalize()
    account_email, sending_email, recipients = process_email_addresses(account_email, sending_email, to_list, cc_list, bcc_list)
    body = process_email_body(body, html_body, tracker, subject, recipients, defines)
    attachments = process_attachments(attachments)

    _send(account_email, sending_email, password, subject, max_send_interval, body, recipients, importance, attachments, defines)
    _log_email_success(subject, sending_email, recipients, defines['DATABASE'])


if __name__ == '__main__':
    main(
        account_email='mhamilton',
        password='Password8',
        subject='aNone',
        body='hi',
        tracker=True,
        importance='high',
        to_list=['mhamilton'],
        defines='DEFINES.yaml'
    )
