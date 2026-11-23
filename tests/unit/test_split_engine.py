"""Unit tests for Exact Integer VND Bill Splitting Engine."""
from app.models import User
from app.schemas.split import SplitBillCreate, SplitItemInput, SplitParticipantInput
from app.services.split_service import SplitService


def test_split_bill_exact_integer_allocation(db_session, demo_session):
    primary_user = db_session.query(User).filter_by(demo_session_id=demo_session.id, role="PRIMARY_USER").first()

    req = SplitBillCreate(
        title="Bữa ăn trưa 180k",
        payer_name="An",
        participants=[
            SplitParticipantInput(display_name="An"),
            SplitParticipantInput(display_name="Bình"),
            SplitParticipantInput(display_name="Cường"),
        ],
        items=[
            SplitItemInput(name="Cơm phần", unit_price_vnd=50000, quantity=3, assigned_participant_names=["An", "Bình", "Cường"]),
            SplitItemInput(name="Nước cam", unit_price_vnd=30000, quantity=1, assigned_participant_names=["An"]),
        ],
        tax_vnd=0,
        service_fee_vnd=0,
        discount_vnd=0,
    )

    res = SplitService.create_split_bill(db_session, demo_session.id, primary_user.id, req)

    assert res.total_bill_amount_vnd == 180000
    shares = {p.display_name: p.total_share_vnd for p in res.participant_shares}

    assert shares["An"] == 80000
    assert shares["Bình"] == 50000
    assert shares["Cường"] == 50000
    assert sum(shares.values()) == 180000


def test_split_bill_remainder_rounding_invariant(db_session, demo_session):
    primary_user = db_session.query(User).filter_by(demo_session_id=demo_session.id, role="PRIMARY_USER").first()

    req = SplitBillCreate(
        title="Chia đều không chia hết",
        payer_name="An",
        participants=[
            SplitParticipantInput(display_name="An"),
            SplitParticipantInput(display_name="Bình"),
            SplitParticipantInput(display_name="Cường"),
        ],
        items=[
            SplitItemInput(name="Món chung", unit_price_vnd=100000, quantity=1, assigned_participant_names=[]),
        ],
        tax_vnd=0,
        service_fee_vnd=0,
        discount_vnd=0,
    )

    res = SplitService.create_split_bill(db_session, demo_session.id, primary_user.id, req)

    shares = [p.total_share_vnd for p in res.participant_shares]
    assert sum(shares) == 100000
    assert 33334 in shares
    assert shares.count(33333) == 2


def test_split_bill_with_tax_and_discounts(db_session, demo_session):
    primary_user = db_session.query(User).filter_by(demo_session_id=demo_session.id, role="PRIMARY_USER").first()

    req = SplitBillCreate(
        title="Hóa đơn có VAT và giảm giá",
        payer_name="An",
        participants=[
            SplitParticipantInput(display_name="An"),
            SplitParticipantInput(display_name="Bình"),
        ],
        items=[
            SplitItemInput(name="Phần của An", unit_price_vnd=60000, quantity=1, assigned_participant_names=["An"]),
            SplitItemInput(name="Phần của Bình", unit_price_vnd=40000, quantity=1, assigned_participant_names=["Bình"]),
        ],
        tax_vnd=10000,
        service_fee_vnd=0,
        discount_vnd=5000,
    )

    res = SplitService.create_split_bill(db_session, demo_session.id, primary_user.id, req)

    assert res.total_bill_amount_vnd == 105000
    shares = {p.display_name: p.total_share_vnd for p in res.participant_shares}
    assert shares["An"] == 63000
    assert shares["Bình"] == 42000
    assert sum(shares.values()) == 105000
