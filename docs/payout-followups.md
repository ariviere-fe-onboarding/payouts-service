# Bank-account follow-up queue

Finance can export a small worklist of reimbursements waiting for bank details:

```sh
python -m payouts.followups --limit 25 > followups.csv
```

The queue contains only `needs_bank_account` payouts, with the oldest reimbursements
first so long-waiting employees receive priority. Equal creation times are ordered
by payout ID. The batch size defaults to 25 and must be between 1 and 100.

CSV columns are payout ID, expense ID, employee ID, integer amount in cents, currency,
and creation time in UTC. The export contains no bank account or routing numbers.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:ff5626d3807e3c3d7ecefa7d35db1aa29dafb879693c0b44437189d6b6aa9db5 -->

An empty queue still produces a header row. Progress goes to stderr.

Text cells beginning with `=`, `+`, `-`, or `@` (also after leading whitespace),
or with a tab, carriage return, or newline, receive a leading apostrophe to keep
them literal when opened in a spreadsheet. CSV quoting alone does not prevent
formula interpretation. Keep that apostrophe when importing into a spreadsheet;
CSV readers may display it as part of the identifier. Stored identifiers are unchanged.

<!-- /coderabbit-ai-generated:v1 -->

Run the command in the payouts service's configured environment. It only reads the
database; it does not send notifications, change payout status, or submit payments.
