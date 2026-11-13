# Payout reconciliation export

Finance can reconcile reimbursement submissions with the bank statement without
querying the database manually. Run this command in the payouts service environment:

```sh
python -m payouts.reconciliation --start-date 2026-11-01 --end-date 2026-11-30 > november-payouts.csv
```

Both dates are inclusive UTC calendar dates. The export is intended to contain only
submitted payouts; reimbursements waiting for bank details and failed payouts do not
represent bank submissions. Rows are ordered by creation time and payout ID.

Columns: payout ID, expense ID, employee ID, integer `amount_cents`, `currency`, ACH
trace ID, and UTC creation time. No bank account or routing numbers are exported.
The command reads the database configured through `get_config()` and does not submit
payments or change payout records. It requires the same database access as the service.

CSV goes to stdout, and a row count goes to stderr so shell redirection produces a
clean file. An empty result still includes the header. Invalid or reversed dates cause
the command to exit with an argument error before opening the database.
