# QCMS v4.14.49 R19 — Send Email timeout fix

- "Email not fully sent: The read operation timed out" is fixed.
  Cause: QCMS waited only 5 seconds for the email server function, but Microsoft 365 SMTP takes about 10 seconds.
  The email WAS delivered (outbox status SENT) - only the screen message was wrong.
- QCMS now waits up to 60 seconds and checks the email outbox for the real result (Sent / Failed / still sending),
  re-triggering the send automatically if it had not started.
