# High-value held-payout totals

Finance can see how many USD reimbursements at or above a chosen amount are waiting
for bank details, and the total value of those held reimbursements:

```sh
python -m payouts.held_totals --minimum-amount-cents 50000
```

The minimum is inclusive: a 50,000-cent minimum includes a payout of exactly
50,000 cents. It defaults to 50,000 cents ($500) and accepts integer values from
1 through 10,000,000, matching the service's supported payout amount range.

The command writes one JSON object containing `currency`, `minimum_amount_cents`,
`payout_count`, and `total_amount_cents`. It includes only `needs_bank_account`
payouts in USD. No qualifying payouts produces a count and total of zero.

Run it in the payouts service's configured environment. This is an aggregate
JSON report for operator dashboards: it contains no employee identifiers or bank
numbers, and does not modify records or submit payments.
