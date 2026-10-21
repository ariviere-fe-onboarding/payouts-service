## Changes

Employees get an email when their payout is submitted, or held because no bank account is on file.

- New `payouts/notify.py` calls the internal notification service after a payout is created.
- Notifications carry the expense ID, amount, currency, and status only, never bank details.

Closes #2

## Validation

- [x] ruff, mypy, bandit, pytest (35 passed), pip-audit
- [x] Tests capture notifications instead of calling the service
