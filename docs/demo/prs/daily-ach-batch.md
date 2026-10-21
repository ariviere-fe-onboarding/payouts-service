## Changes

Payouts now go out in one daily ACH batch instead of one submission per approval, to cut per-submission bank fees.

- The webhook schedules the payout (`scheduled`) instead of submitting it.
- New `python -m payouts.batch` command submits everything scheduled before the 17:00 cutoff.
- The webhook contract with expense-app is unchanged; expense-app shows the new status as-is.

Closes #1

## Validation

- [x] ruff, mypy, bandit, pytest (36 passed), pip-audit
- [x] New batch tests for the cutoff and for skipping already-submitted payouts
