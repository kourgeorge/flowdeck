"""Admin-only routes that live outside routers/admin.py.

test_admin_regressions only walks admin.router.routes, so the two money routes
elsewhere (top-up adds any amount to the caller's balance; major-stocks sync
starts paid analyses) had no guard against a dropped get_current_admin_user.
"""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import database
from auth import create_access_token
from models.db_models import ApiKey, User
from routers import analyses, me
from services import token_service

TOP_UP = '/api/tokens/top-up'
SYNC = '/api/sync/major-stocks'


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path}/routes.db', connect_args={'check_same_thread': False})
    event.listen(engine, 'connect', database._set_sqlite_pragmas)
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    db.add_all([User(id=1, email='admin@example.test', is_admin=True), User(id=2, email='user@example.test')])
    db.commit()

    # The sync route must never reach the real ticker lookup, analysis service
    # or background runner; any call past the auth check is recorded here.
    sync_calls = []
    monkeypatch.setattr(analyses, 'get_missing_and_skipped',
                        lambda date: sync_calls.append(('lookup', date)) or (['AAPL'], []))
    monkeypatch.setattr(analyses.app_services, 'get_analysis_service', lambda: object())
    monkeypatch.setattr(analyses, 'run_sync_major_tickers_background',
                        lambda *args: sync_calls.append(('background', args)))

    app = FastAPI()
    app.include_router(me.router)
    app.include_router(analyses.router)

    def get_db():
        with factory() as session:
            yield session
    app.dependency_overrides[database.get_db] = get_db
    admin_headers = {'Authorization': 'Bearer ' + create_access_token(db.get(User, 1).auth_subject)}
    user_headers = {'Authorization': 'Bearer ' + create_access_token(db.get(User, 2).auth_subject)}
    with patch.object(database, 'SessionLocal', factory), TestClient(app, raise_server_exceptions=False) as client:
        yield db, client, admin_headers, user_headers, sync_calls
    db.close()
    engine.dispose()


def _balance(db, user_id):
    db.expire_all()
    return token_service.get_balance(user_id, db)


def _user_api_key_headers(db):
    plain, hashed = ApiKey.generate_key()
    db.add(ApiKey(user_id=2, user_subject=db.get(User, 2).auth_subject, key_hash=hashed,
                  key_prefix=plain[:16], name='review'))
    db.commit()
    return {'Authorization': 'Bearer ' + plain}


def test_top_up_without_auth_returns_401(ctx):
    _, client, _, _, _ = ctx
    assert client.post(TOP_UP, json={'amount': 500}).status_code == 401


def test_sync_without_auth_returns_401_and_starts_nothing(ctx):
    _, client, _, _, sync_calls = ctx
    assert client.post(SYNC, json={}).status_code == 401
    assert sync_calls == []


def test_top_up_with_normal_user_jwt_returns_403_and_keeps_balance(ctx):
    db, client, _, user_headers, _ = ctx
    before = _balance(db, 2)
    assert client.post(TOP_UP, headers=user_headers, json={'amount': 500}).status_code == 403
    assert _balance(db, 2) == before


def test_sync_with_normal_user_jwt_returns_403_and_starts_nothing(ctx):
    _, client, _, user_headers, sync_calls = ctx
    assert client.post(SYNC, headers=user_headers, json={}).status_code == 403
    assert sync_calls == []


def test_top_up_with_normal_user_api_key_returns_403_and_keeps_balance(ctx):
    db, client, _, _, _ = ctx
    headers = _user_api_key_headers(db)
    before = _balance(db, 2)
    assert client.post(TOP_UP, headers=headers, json={'amount': 500}).status_code == 403
    assert _balance(db, 2) == before


def test_sync_with_normal_user_api_key_returns_403_and_starts_nothing(ctx):
    db, client, _, _, sync_calls = ctx
    headers = _user_api_key_headers(db)
    assert client.post(SYNC, headers=headers, json={}).status_code == 403
    assert sync_calls == []


def test_admin_top_up_of_500_returns_200_and_adds_500(ctx):
    db, client, admin_headers, _, _ = ctx
    before = _balance(db, 1)
    response = client.post(TOP_UP, headers=admin_headers, json={'amount': 500})
    assert response.status_code == 200, response.text
    assert response.json()['token_balance'] == before + 500
    assert _balance(db, 1) == before + 500


def test_admin_top_up_of_zero_returns_400_and_keeps_balance(ctx):
    db, client, admin_headers, _, _ = ctx
    before = _balance(db, 1)
    assert client.post(TOP_UP, headers=admin_headers, json={'amount': 0}).status_code == 400
    assert _balance(db, 1) == before


def test_admin_sync_returns_200_using_the_patched_background_work(ctx):
    _, client, admin_headers, _, sync_calls = ctx
    response = client.post(SYNC, headers=admin_headers, json={'analysis_date': '2026-01-02'})
    assert response.status_code == 200, response.text
    assert response.json() == {'date': '2026-01-02', 'triggered': ['AAPL'], 'skipped': []}
    assert [call[0] for call in sync_calls] == ['lookup', 'background']
