"""PayPal reconciliation and the execute-timeout recovery path, with a fake PayPal and temporary SQLite.

reconcile_payments() is the only way a paid order whose local credit failed (or
whose browser closed before /execute) ever gets its tokens, so it must credit
exactly once, expire stale orders and survive PayPal errors without losing state.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import database
from models.db_models import PaymentOrder, Usage, User
from services import paypal_service as service
from services import token_service


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.sqlite'}", connect_args={'check_same_thread': False})
    event.listen(engine, 'connect', database._set_sqlite_pragmas)
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    # reconcile_payments imports SessionLocal from database at call time.
    monkeypatch.setattr(database, 'SessionLocal', sessions)
    # reconcile_payments returns early unless credentials are set.
    monkeypatch.setattr(service, 'PAYPAL_CLIENT_ID', 'test-client')
    monkeypatch.setattr(service, 'PAYPAL_CLIENT_SECRET', 'test-secret')
    with sessions() as db:
        db.add(User(id=1, email='buyer@example.invalid'))
        db.commit()
        subject = db.get(User, 1).auth_subject
    yield SimpleNamespace(engine=engine, sessions=sessions, subject=subject)
    engine.dispose()


def _fake_payment(subject, payment_id='PAY-test', state='approved', sale_state='completed'):
    amount = SimpleNamespace(total='5.00', currency='USD')
    resources = []
    if sale_state is not None:
        resources = [SimpleNamespace(sale=SimpleNamespace(id='SALE-test', state=sale_state, amount=amount))]
    return SimpleNamespace(id=payment_id, state=state, transactions=[SimpleNamespace(
        custom=f'{subject}:starter:500', amount=amount, related_resources=resources)])


def _add_order(runtime, payment_id='PAY-test', status='created', created_at=None):
    with runtime.sessions() as db:
        order = PaymentOrder(payment_id=payment_id, user_id=1, package_id='starter',
                             tokens=500, amount='5.00', status=status)
        if created_at is not None:
            order.created_at = created_at
            order.updated_at = created_at
        db.add(order)
        db.commit()


def _purchase_count(runtime):
    with runtime.sessions() as db:
        return db.query(Usage).filter_by(transaction_type='purchase').count()


def _order(runtime, payment_id='PAY-test'):
    with runtime.sessions() as db:
        order = db.get(PaymentOrder, payment_id)
        db.expunge(order)
        return order


def test_reconcile_credits_captured_order_once(runtime, monkeypatch):
    _add_order(runtime, status='captured')
    payment = _fake_payment(runtime.subject)
    payment.execute = Mock(side_effect=AssertionError('reconcile must never execute a sale'))
    monkeypatch.setattr(service.paypalrestsdk.Payment, 'find', lambda _id: payment)

    service.reconcile_payments()
    assert _order(runtime).status == 'credited'
    assert _purchase_count(runtime) == 1
    with runtime.sessions() as db:
        assert token_service.get_balance_from_ledger(1, db) == 500

    service.reconcile_payments()
    assert _purchase_count(runtime) == 1
    with runtime.sessions() as db:
        assert token_service.get_balance_from_ledger(1, db) == 500


def test_reconcile_expires_unapproved_order_older_than_30_days(runtime, monkeypatch):
    _add_order(runtime, created_at=datetime.utcnow() - timedelta(days=31))
    payment = _fake_payment(runtime.subject, state='created', sale_state=None)
    monkeypatch.setattr(service.paypalrestsdk.Payment, 'find', lambda _id: payment)

    service.reconcile_payments()

    assert _order(runtime).status == 'expired'
    assert _purchase_count(runtime) == 0


def test_reconcile_keeps_recent_unapproved_order_created(runtime, monkeypatch):
    _add_order(runtime, created_at=datetime.utcnow() - timedelta(days=29))
    payment = _fake_payment(runtime.subject, state='created', sale_state=None)
    monkeypatch.setattr(service.paypalrestsdk.Payment, 'find', lambda _id: payment)

    service.reconcile_payments()

    assert _order(runtime).status == 'created'
    assert _purchase_count(runtime) == 0


def test_reconcile_records_error_when_paypal_lookup_fails(runtime, monkeypatch):
    _add_order(runtime)

    def find(_id):
        raise ConnectionError('PayPal unreachable')
    monkeypatch.setattr(service.paypalrestsdk.Payment, 'find', find)

    service.reconcile_payments()

    order = _order(runtime)
    assert order.status == 'created'
    assert 'PayPal unreachable' in order.error_message
    assert _purchase_count(runtime) == 0


def test_reconcile_does_nothing_without_paypal_credentials(runtime, monkeypatch):
    _add_order(runtime, status='captured')
    monkeypatch.setattr(service, 'PAYPAL_CLIENT_ID', None)
    find = Mock()
    monkeypatch.setattr(service.paypalrestsdk.Payment, 'find', find)

    service.reconcile_payments()

    assert find.call_count == 0
    assert _order(runtime).status == 'captured'


def test_execute_timeout_after_remote_capture_credits_once(runtime, monkeypatch):
    _add_order(runtime)
    before = _fake_payment(runtime.subject, state='created', sale_state=None)
    before.execute = Mock(side_effect=TimeoutError('read timed out'))
    after = _fake_payment(runtime.subject)
    after.execute = Mock(side_effect=AssertionError('must not recapture'))
    lookups = iter([before, after, after])
    monkeypatch.setattr(service.paypalrestsdk.Payment, 'find', lambda _id: next(lookups))

    with runtime.sessions() as db:
        result = service.execute_payment('PAY-test', 'payer', db, user_id=1)
        assert result['tokens_credited'] == 500
        # A browser retry after the timeout must not credit again.
        assert service.execute_payment('PAY-test', 'payer', db, user_id=1)['success']

    assert before.execute.call_count == 1
    assert _order(runtime).status == 'credited'
    assert _purchase_count(runtime) == 1


def _not_captured_payment(runtime, monkeypatch):
    _add_order(runtime)
    payment = _fake_payment(runtime.subject, state='created', sale_state=None)
    payment.execute = Mock(return_value=False)
    monkeypatch.setattr(service.paypalrestsdk.Payment, 'find', lambda _id: payment)
    return payment


def test_execute_not_captured_raises_and_credits_nothing(runtime, monkeypatch):
    _not_captured_payment(runtime, monkeypatch)

    with runtime.sessions() as db:
        with pytest.raises(RuntimeError):
            service.execute_payment('PAY-test', 'payer', db, user_id=1)

    assert _order(runtime).status == 'created'
    assert _purchase_count(runtime) == 0


def test_execute_endpoint_returns_500_when_not_captured(runtime, monkeypatch):
    from auth import get_current_user
    from routers import payments
    _not_captured_payment(runtime, monkeypatch)
    app = FastAPI()
    app.include_router(payments.router)

    def get_db():
        with runtime.sessions() as db:
            yield db
    app.dependency_overrides[database.get_db] = get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)

    response = TestClient(app).post('/api/payments/execute', params={'payment_id': 'PAY-test', 'PayerID': 'payer'})

    assert response.status_code == 500
    assert _purchase_count(runtime) == 0
