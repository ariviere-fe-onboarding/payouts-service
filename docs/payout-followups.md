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
An empty queue still produces a header row. Progress goes to stderr.

Run the command in the payouts service's configured environment. It only reads the
database; it does not send notifications, change payout status, or submit payments.
