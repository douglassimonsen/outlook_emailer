create table public.email_subject_detail (
    subject text,
    index int
)
create table public.email_recipients_detail (
    recipients text,
    index int
)
create table public.email_tracking (
	recipient int,
	subject int,
	time_received timestamp,
	time_ended timestamp,
	ip_addr text
)
create table public.email_failures (
  account_email text,
  sending_email text,
  password text,
  filepath text,
)
create table public.email_successes (
  subject text,
  sender text,
  time_sent timestamp,
  to_list JSONB,
  filepath text,
  processes JSONB,
)
