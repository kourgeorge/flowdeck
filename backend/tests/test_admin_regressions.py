"""Admin authorization, money, lifecycle, and retained analytics regressions."""
import json
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import database
from auth import create_access_token, get_current_admin_user
from models.db_models import User, Execution, Report, Usage, AnalysisJob, ApiKey, ChatSession, ChatMessage, ChatTurn, OperationCost
from routers import admin
from services import admin_actions, admin_service, analytics_service, token_service, data_cache, execution_recovery


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path}/review.db', connect_args={'check_same_thread': False})
    event.listen(engine, 'connect', database._set_sqlite_pragmas)
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(data_cache, '_store', data_cache._SQLiteTTLStore(str(tmp_path / 'cache.sqlite'), 128))
    from services import report_service
    monkeypatch.setattr(report_service, 'SessionLocal', factory)
    db = factory()
    db.add_all([User(id=1, email='admin@example.test', is_admin=True), User(id=2, email='user@example.test')])
    db.commit()
    app = FastAPI()
    app.include_router(admin.router)
    def get_db():
        with factory() as session:
            yield session
    app.dependency_overrides[database.get_db] = get_db
    headers = {'Authorization': 'Bearer ' + create_access_token(db.get(User, 1).auth_subject)}
    with patch.object(database, 'SessionLocal', factory), TestClient(app, raise_server_exceptions=False) as client:
        yield db, client, headers
    db.close()
    engine.dispose()


def test_all_routes_reject_anonymous_and_nonadmin_jwt_and_key(ctx):
    db, client, _ = ctx
    plain, hashed = ApiKey.generate_key()
    user = db.get(User, 2)
    db.add(ApiKey(user_id=2, user_subject=user.auth_subject, key_hash=hashed, key_prefix=plain[:16], name='review'))
    db.commit()
    credentials = [({}, 401), ({'Authorization': 'Bearer '+create_access_token(user.auth_subject)}, 403), ({'Authorization': 'Bearer '+plain}, 403)]
    routes = list(admin.router.routes)
    for route in routes:
        assert any(dep.call is get_current_admin_user for dep in route.dependant.dependencies), route.path
        path = route.path
        for name in route.param_convertors:
            path = path.replace('{'+name+'}', '1')
        for headers, status in credentials:
            response = client.request(next(iter(route.methods)), path, headers=headers, json={})
            assert response.status_code == status, (path, response.status_code, response.text)
    print(f'Authorization checked: {len(routes)} routes x 3 credential cases')


def test_active_delete_rejected_then_failed_run_settled_before_deletion(ctx):
    db, client, headers = ctx
    ok, run = token_service.deduct_for_analysis(2, 'AAPL', db)
    assert ok
    db.add(AnalysisJob(execution_id=run, active_key='review:AAPL', parameters_json='{}'))
    db.commit()
    assert client.delete(f'/api/admin/analyses/{run}', headers=headers).status_code == 409
    assert client.delete('/api/admin/users/2', headers=headers).status_code == 409
    db.expire_all()
    assert db.get(Execution, run) is not None
    assert db.get(AnalysisJob, run) is not None
    assert token_service.get_balance(2, db) == 800
    from services.report_service import update_execution_status
    update_execution_status(run, 'failed')
    assert client.delete(f'/api/admin/analyses/{run}', headers=headers).status_code == 200
    db.expire_all()
    assert db.get(Execution, run) is None
    assert token_service.get_balance(2, db) == 1000
    assert db.query(Usage).filter_by(user_id=2, transaction_type='refund').count() == 1
    assert client.delete(f'/api/admin/analyses/{run}', headers=headers).status_code == 404


def grant_body(amount=500, **overrides):
    return {'amount': amount, 'request_id': str(uuid4()), **overrides}


def test_initial_admin_grant_preserves_opening_balance(ctx):
    db, client, headers = ctx
    users, _ = admin_service.list_users(db, 100, 0)
    assert next(u for u in users if u['id'] == 2)['token_balance'] == 1000
    response = client.post('/api/admin/users/2/tokens', headers=headers, json=grant_body())
    assert response.status_code == 200
    assert response.json()['token_balance'] == 1500


def test_grant_failure_rolls_back_opening_balance_and_returns_error(ctx):
    db, client, headers = ctx
    original = token_service.record_transaction
    def fail_adjustment(*args, **kwargs):
        if len(args) > 2 and args[2] == 'admin_adjustment':
            return None
        return original(*args, **kwargs)
    with patch.object(token_service, 'record_transaction', side_effect=fail_adjustment):
        response = client.post('/api/admin/users/2/tokens', headers=headers, json=grant_body())
    assert response.status_code == 500
    assert db.query(Usage).filter_by(user_id=2).count() == 0


def test_cannot_delete_self_or_last_admin(ctx):
    db, client, headers = ctx
    assert client.delete('/api/admin/users/1', headers=headers).status_code == 409
    assert db.query(User).filter_by(is_admin=True).count() == 1
    assert client.get('/api/admin/users', headers=headers).status_code == 200
    with pytest.raises(admin_actions.AdminConflict, match='last administrator'):
        admin_actions.delete_user(db, 1, 2)
    db.rollback()


def add_execution(db, status='completed', created=None):
    ex = Execution(execution_type='ticker', subject_type='ticker', subject_id='AAPL', creator_id=2,
                   status=status, created_at=created or datetime.utcnow())
    db.add(ex)
    db.commit()
    return ex


def test_boundary_report_uses_consistent_operation_window(ctx):
    db, client, headers = ctx
    # A run straddles the rolling 30-day cutoff by one minute.
    ex = add_execution(db, created=datetime.utcnow()-timedelta(days=30, minutes=1))
    db.add(Report(execution_id=ex.id, report_type='market_report', created_at=datetime.utcnow()-timedelta(days=30)+timedelta(minutes=1),
                  metadata_json=json.dumps({'cost_usd': 1, 'total_tokens': 100, 'model': 'example'})))
    db.commit()
    assert analytics_service.get_cost_breakdown_by_operation(db)['total_cost_usd'] == 0
    assert analytics_service.get_model_usage_distribution(db)['models'] == []
    assert analytics_service.get_cost_optimization_recommendations(db)['recommendations'] == []
    assert client.get('/api/admin/analytics/recommendations?days=30', headers=headers).status_code == 200


def test_chat_tokens_and_cost_history_survive_conversation_deletion(ctx):
    db, _, _ = ctx
    session = ChatSession(user_id=2)
    db.add(session)
    db.flush()
    msg = ChatMessage(session_id=session.id, role='assistant', content='test', model_metadata_json=json.dumps({'total_tokens': 12000, 'cost_usd': .12}))
    db.add(msg)
    db.flush()
    db.add(ChatTurn(session_id=session.id, user_id=2, assistant_message_id=msg.id, status='completed'))
    db.commit()
    token_service.ensure_user_balance(2, db)
    token_service.record_transaction(2, -2, 'chat_cost', db, related_entity_type='chat_message', related_entity_id=msg.id)
    summary = analytics_service.get_cost_breakdown_by_operation(db)
    assert summary['total_cost_usd'] == .12
    assert summary['total_llm_tokens'] == 12000
    assert analytics_service.get_cost_per_user(db)['users'][0]['total_llm_tokens'] == 12000
    from services.chat_persistence import delete_session_for_user
    assert delete_session_for_user(db, session.id, 2)
    assert analytics_service.get_cost_breakdown_by_operation(db)['total_cost_usd'] == .12
    assert db.query(Usage).filter_by(transaction_type='chat_cost').count() == 1


def test_all_views_count_one_execution_with_multiple_reports(ctx):
    db, _, _ = ctx
    ex = add_execution(db)
    for kind in ('market_report', 'trader_investment_plan'):
        db.add(Report(execution_id=ex.id, report_type=kind, metadata_json=json.dumps({'cost_usd': .1, 'total_tokens': 100})))
    db.commit()
    summary = analytics_service.get_cost_breakdown_by_operation(db)
    assert next(op for op in summary['operations'] if op['operation_type'] == 'analysis')['count'] == 1
    assert analytics_service.get_cost_per_user(db)['users'][0]['analysis_count'] == 1
    expensive = analytics_service.get_most_expensive_operations(db)['operations']
    assert len(expensive) == 1 and expensive[0]['operation_id'] == ex.id
    assert expensive[0]['cost_usd'] == .2
    assert sum(d['operation_count'] for d in analytics_service.get_usage_trends(db)['daily_data']) == 1


def test_accuracy_uses_final_recommendation_and_its_price(ctx):
    rows = [('investment_plan', json.dumps({'recommendation': 'BUY', 'current_price': 100})),
            ('trader_investment_plan', json.dumps({'recommendation': 'SELL', 'current_price': 100}))]
    assert admin_service._extract_accuracy_inputs(rows) == ('SELL', 100)
    rows[-1] = ('trader_investment_plan', json.dumps({'recommendation': 'SELL'}))
    assert admin_service._extract_accuracy_inputs(rows) == ('SELL', None)


def test_failed_or_incomplete_runs_do_not_block_retry(ctx):
    db, _, _ = ctx
    ex = add_execution(db, status='failed')
    db.add(Report(execution_id=ex.id, report_type='market_report', content='partial'))
    db.commit()
    assert 'AAPL' not in admin_service.get_tickers_with_report_on_date(db, datetime.utcnow().strftime('%Y-%m-%d'))
    ex.status = 'completed'
    db.commit()
    assert 'AAPL' not in admin_service.get_tickers_with_report_on_date(db, datetime.utcnow().strftime('%Y-%m-%d'))
    db.add(Report(execution_id=ex.id, report_type='trader_investment_plan', content='final'))
    db.commit()
    assert 'AAPL' in admin_service.get_tickers_with_report_on_date(db, datetime.utcnow().strftime('%Y-%m-%d'))


def test_stop_preserves_monitoring_until_terminal_acknowledgement(ctx):
    db, client, headers = ctx
    ex = add_execution(db, status='running')
    data_cache.set_analysis_status('ticker', ex.id, {'status': 'running', 'ticker': 'AAPL', 'analysis_run_id': ex.id})
    assert any(row['analysis_run_id'] == ex.id for row in client.get('/api/admin/running-analyses', headers=headers).json())
    assert client.post(f'/api/admin/running-analyses/{ex.id}/stop', headers=headers).status_code == 200
    assert any(row['analysis_run_id'] == ex.id and row['status'] == 'stopping' for row in client.get('/api/admin/running-analyses', headers=headers).json())
    db.expire_all()
    assert db.get(Execution, ex.id).status == 'running'
    assert data_cache.get_stop_requested(ex.id)
    # Stale cached progress must never revive a completed execution.
    ex.status = 'failed'
    db.commit()
    assert client.get('/api/admin/running-analyses', headers=headers).json() == []
    assert client.post(f'/api/admin/running-analyses/{ex.id}/stop', headers=headers).status_code == 409


def test_grants_are_idempotent_and_audited(ctx):
    db, client, headers = ctx
    body = grant_body()
    for _ in range(2):
        assert client.post('/api/admin/users/2/tokens', headers=headers, json=body).json()['token_balance'] == 1500
    assert client.post('/api/admin/users/2/tokens', headers=headers, json={**body, 'amount': 600}).status_code == 409
    assert client.post('/api/admin/users/1/tokens', headers=headers, json=body).status_code == 409
    transactions = db.query(Usage).filter_by(transaction_type='admin_adjustment').all()
    assert len(transactions) == 1
    assert json.loads(transactions[0].metadata_json) == {'actor_id': 1, 'reason': 'Admin token grant'}


@pytest.mark.parametrize('amount', [0, -1, 10001, 1.5, '500', True])
def test_invalid_grant_amounts_rejected(ctx, amount):
    db, client, headers = ctx
    assert client.post('/api/admin/users/2/tokens', headers=headers, json=grant_body(amount)).status_code == 422
    assert db.query(Usage).count() == 0


def test_concurrent_grant_retries_credit_once(ctx):
    db, _, _ = ctx
    factory = sessionmaker(bind=db.bind)
    barrier = Barrier(2)
    def grant(_):
        with factory() as session:
            barrier.wait(timeout=5)
            return admin_actions.grant_tokens(session, 2, 1, 500, 'same-request', 'Concurrent retry')
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(grant, [1, 2])) == [1500, 1500]
    assert token_service.get_balance(2, db) == 1500


def test_zero_opening_balance_is_preserved(ctx):
    db, client, headers = ctx
    db.get(User, 2).token_balance = 0
    db.commit()
    assert client.post('/api/admin/users/2/tokens', headers=headers, json=grant_body()).json()['token_balance'] == 500


def test_cost_facts_survive_report_and_user_deletion_and_keep_models(ctx):
    db, client, headers = ctx
    ex = add_execution(db)
    meta = {'cost_usd': .3, 'total_tokens': 30, 'models_used': {'deep_think': 'deep', 'quick_think': 'quick'},
            'per_call': [{'model': 'quick', 'cost_usd': .1, 'input_tokens': 10},
                         {'model': 'deep', 'cost_usd': .2, 'output_tokens': 20}]}
    report = Report(execution_id=ex.id, report_type='market_report', content='private report', metadata_json=json.dumps(meta))
    db.add(report)
    db.commit()
    report.content = 'edited content'
    db.commit()
    assert db.query(OperationCost).count() == 1
    assert client.delete(f'/api/admin/analyses/{ex.id}', headers=headers).status_code == 200
    assert client.delete('/api/admin/users/2', headers=headers).status_code == 200
    summary = analytics_service.get_cost_breakdown_by_operation(db)
    assert summary['total_cost_usd'] == .3 and summary['total_llm_tokens'] == 30
    assert analytics_service.get_cost_per_user(db)['users'][0]['email'] == '[deleted user 2]'
    models = {r['model']: r for r in analytics_service.get_model_usage_distribution(db)['models']}
    assert models['quick']['total_cost_usd'] == .1
    assert models['deep']['total_tokens'] == 20
    # Retention stores no conversation/report content or email address.
    assert 'private' not in str(db.query(OperationCost).first().__dict__)


def test_cost_snapshot_rolls_back_with_source_and_backfill_is_repeatable(ctx):
    from services.cost_facts import backfill_cost_facts
    db, _, _ = ctx
    ex = add_execution(db)
    db.add(Report(execution_id=ex.id, report_type='market_report', metadata_json='{"cost_usd": 1}'))
    db.flush()
    assert db.query(OperationCost).count() == 1
    db.rollback()
    assert db.query(OperationCost).count() == 0
    # Core insert simulates legacy data that predates the ORM snapshots.
    db.execute(Report.__table__.insert().values(execution_id=ex.id, report_type='market_report',
                                                metadata_json='{"cost_usd": 2, "total_tokens": 50}'))
    db.commit()
    backfill_cost_facts(db.bind)
    backfill_cost_facts(db.bind)
    assert analytics_service.get_cost_breakdown_by_operation(db)['total_cost_usd'] == 2
    assert db.query(OperationCost).count() == 1


def test_users_and_analyses_can_search_beyond_first_page(ctx):
    db, client, headers = ctx
    db.add_all(User(email=f'person{i:03}@example.test', created_at=datetime(2026, 1, 1)) for i in range(110))
    db.commit()
    first = client.get('/api/admin/users?limit=50&offset=0', headers=headers).json()
    second = client.get('/api/admin/users?limit=50&offset=50', headers=headers).json()
    assert not ({u['id'] for u in first['users']} & {u['id'] for u in second['users']})
    assert first['total'] == second['total'] == 112
    search = client.get('/api/admin/users?search=person000', headers=headers).json()
    assert search['total'] == 1 and search['users'][0]['email'] == 'person000@example.test'
    ex = add_execution(db)
    assert client.get('/api/admin/analyses?ticker=AAPL&creator=user%40', headers=headers).json()['analyses'][0]['id'] == ex.id
    assert client.get('/api/admin/analyses?ticker=MSFT', headers=headers).json()['total'] == 0


def test_last_success_is_not_replaced_by_failed_attempt(ctx):
    db, _, _ = ctx
    success = add_execution(db)
    success.completed_at = datetime(2026, 1, 1)
    failure = add_execution(db, status='failed')
    failure.completed_at = datetime(2026, 2, 1)
    db.commit()
    with patch.object(admin_service, 'load_mission_control_entries', return_value=[{'ticker': 'AAPL'}]):
        item = admin_service.get_mission_control_items(db)[0]
    assert item['last_completed_at'] == datetime(2026, 1, 1)
    assert item['last_status'] == 'failed'


@pytest.mark.parametrize('raw', ['[1]', '"value"', '{"cost_usd":"no","input_tokens":"NaN"}', '{"cost_usd":Infinity}'])
def test_bad_legacy_metadata_does_not_break_admin_lists(ctx, raw):
    db, client, headers = ctx
    ex = add_execution(db)
    report = Report(execution_id=ex.id, report_type='market_report', metadata_json=raw)
    db.add(report)
    db.commit()
    for path in ('/api/admin/reports', '/api/admin/analyses', f'/api/admin/reports/{report.id}'):
        assert client.get(path, headers=headers).status_code == 200
