# Held reimbursement follow-up report

Finance needs a weekly worklist of employees whose approved reimbursements are
waiting for bank details. Generate it inside the payouts service environment:

```sh
python -m payouts.aging --as-of 2026-11-13 --min-age-days 7 > held-payouts.json
```

The report includes payouts currently in `needs_bank_account` status whose age is
at least the requested number of UTC calendar days. For example, on November 13,
a payout created on November 6 is seven days old and qualifies for a seven-day
report. A minimum of zero includes payouts created on the reporting date.

Each employee/currency entry contains the qualifying expense IDs, payout count,
total in integer cents, and the age of their oldest qualifying reimbursement.
Employees with the longest wait appear first, with employee ID and currency as
stable tie-breakers. Future-dated, submitted, and failed payouts are excluded.

This is a snapshot of current statuses using the supplied date to calculate ages,
not a reconstruction of historical payout states. No account or routing numbers
appear in the JSON. The command uses `get_config()` and the service's database
access; it sends no reminders and changes no payout state.
