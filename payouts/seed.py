"""Seed synthetic bank accounts for the demo employees. Run: python -m payouts.seed."""

from __future__ import annotations

from sqlalchemy.orm import Session

from payouts.config import get_config
from payouts.crypto import FieldCipher
from payouts.db import Base, make_engine, make_session_factory
from payouts.models import BankAccount

# Synthetic numbers. 110000000 is a test routing number; none of these accounts exist.
DEMO_ACCOUNTS: tuple[tuple[str, str, str, str], ...] = (
    ("emp-priya", "Harbor Credit Union", "110000000", "000123456789"),
    ("emp-marcus", "Harbor Credit Union", "110000000", "000987654321"),
    ("emp-lena", "Harbor Credit Union", "110000000", "000222033344"),
    ("emp-jonah", "Lakeside Bank", "110000000", "000555012345"),
    ("emp-dana", "Lakeside Bank", "110000000", "000444098765"),
)


def seed(session: Session, cipher: FieldCipher) -> int:
    """Insert any missing demo accounts and return how many were added."""
    added = 0
    for employee_id, bank_name, routing, account in DEMO_ACCOUNTS:
        if session.get(BankAccount, employee_id) is not None:
            continue
        session.add(
            BankAccount(
                employee_id=employee_id,
                bank_name=bank_name,
                routing_number_encrypted=cipher.encrypt(routing),
                account_number_encrypted=cipher.encrypt(account),
                account_last4=account[-4:],
            )
        )
        added += 1
    session.commit()
    return added


def main() -> None:
    """Seed the configured database."""
    config = get_config()
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        added = seed(session, FieldCipher(config.encryption_key))
    print(f"Seeded {added} bank accounts.")


if __name__ == "__main__":
    main()
