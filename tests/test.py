import sys
import pathlib
import exchangelib
import datetime
import time
import os
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import outlook_emailer  # noqa
email_addr = os.environ["TEST_EMAIL_ADDR"]


def test_emailer():
    outlook_emailer.send_email(
        account_email=email_addr,
        to_list=[email_addr],
        subject="Test Passed!"
    )


def test_access():
    outlook_emailer.get_exchangelib_account(access_account=email_addr)


def test_emailer_skip():
    tz = exchangelib.EWSTimeZone.localzone()
    now = datetime.datetime.today()
    subject = "email_test_" + now.strftime("%Y_%m_%d_%H_%M_%S_%f")
    outlook_emailer.send_email(account_email=email_addr, to_list=[email_addr], subject=subject)
    time.sleep(15)  # this is necessary because the server takes a second to log a sent email
    outlook_emailer.send_email(account_email=email_addr, to_list=[email_addr], subject=subject, max_send_interval="daily")

    account = outlook_emailer.get_exchangelib_account(access_account=email_addr)
    now = tz.localize(exchangelib.EWSDateTime.fromtimestamp(tz.localize(now).timestamp()))
    cnt = account.sent.filter(datetime_received__gte=now, subject=subject).count()
    assert cnt <= 1  # occasionally neither register in time
