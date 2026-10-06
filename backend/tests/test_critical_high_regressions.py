"""Security and money invariants, using isolated files and fake external services."""
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

import database
from models.db_models import (ApiKey, ChatMessage, ChatSession, ChatTurn, Execution,
                              OAuthState, PaymentOrder, Usage, User, UserProfile)
from services import token_service


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.sqlite'}", connect_args={'check_same_thread': False})
    event.listen(engine, 'connect', database._set_sqlite_pragmas)
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, 'SessionLocal', sessions)
    from services import report_service, chat_turn_service, data_cache
    monkeypatch.setattr(report_service, 'SessionLocal', sessions)
    monkeypatch.setattr(chat_turn_service, 'SessionLocal', sessions)
    monkeypatch.setattr(data_cache, '_store', data_cache._SQLiteTTLStore(str(tmp_path / 'cache.sqlite'), 128))
    with sessions() as db:
        db.add_all([User(id=1, email='first@example.invalid'), User(id=2, email='second@example.invalid')])
        db.commit()
    yield SimpleNamespace(engine=engine, sessions=sessions)
    engine.dispose()


def test_deleted_account_data_and_credentials_never_attach_to_replacement(runtime):
    from auth import create_access_token, get_current_user_optional
    from services.api_key_service import create
    from services.auth_service import delete_account
    with runtime.sessions() as db:
        user = db.get(User, 2)
        jwt = create_access_token(user.auth_subject)
        _, key = create(db, user.id, 'test')
        session = ChatSession(user_id=user.id)
        db.add(session)
        db.flush()
        db.add(ChatMessage(session_id=session.id, role='user', content='private'))
        token_service.record_transaction(user.id, 10, 'initial_balance', db)
        delete_account(user, None, db)
        assert db.query(ChatMessage).count() == db.query(ChatSession).count() == db.query(ApiKey).count() == 0
        assert db.query(Usage).filter_by(user_id=2).count() == 0
        # Force reuse to prove security does not rely on monotonically increasing IDs.
        db.add(User(id=2, email='replacement@example.invalid'))
        db.commit()
        for credential in (jwt, key):
            assert get_current_user_optional(HTTPAuthorizationCredentials(scheme='Bearer', credentials=credential), db) is None


def test_migration_revokes_legacy_keys_and_is_repeatable(tmp_path):
    from schema_migrations import migrate
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite'}")
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)')
        c.exec_driver_sql('CREATE TABLE api_keys (id INTEGER PRIMARY KEY, user_id INTEGER, is_active BOOLEAN)')
        c.exec_driver_sql('CREATE TABLE usage (id INTEGER PRIMARY KEY, user_id INTEGER)')
        c.exec_driver_sql("INSERT INTO users VALUES (1, 'legacy@example.invalid')")
        c.exec_driver_sql('INSERT INTO api_keys VALUES (1, 1, 1)')
    # create_all creates remaining tables, matching upgrade startup ordering.
    database.Base.metadata.create_all(engine)
    migrate(engine)
    migrate(engine)
    with engine.connect() as c:
        assert c.exec_driver_sql('SELECT length(auth_subject) FROM users').scalar() >= 32
        assert c.exec_driver_sql('SELECT is_active FROM api_keys').scalar() == 0
    engine.dispose()


def test_concurrent_debits_cannot_overspend_and_replays_do_not_repeat(runtime):
    with runtime.sessions() as db:
        token_service.record_transaction(1, 1000, 'initial_balance', db)
    barrier = threading.Barrier(2)
    def debit(index):
        with runtime.sessions() as db:
            barrier.wait(timeout=5)
            return token_service.record_transaction(1, -700, 'analysis_cost', db,
                operation_key=f'debit:{index}') is not None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(debit, [1, 2]))
    assert sorted(results) == [False, True]
    with runtime.sessions() as db:
        assert token_service.get_balance_from_ledger(1, db) == 300
        token_service.record_transaction(1, 1000, 'initial_balance', db)
        assert token_service.get_balance_from_ledger(1, db) == 300


def test_cached_graph_tools_use_each_invocations_user_for_reads_and_writes(runtime, monkeypatch):
    from ai_engine.agent.graph import FlowDeckAgent
    from ai_engine.agent.lc_tools import make_user_lc_tools
    from ai_engine.agent.tool import ExecutionContext
    from ai_engine.agent.tools.user_context import UserContextTool, ToolResult
    from langchain_core.messages import AIMessage
    identities = []
    def read(self, ctx, **kwargs):
        identities.append(ctx.user_id)
        return ToolResult(ok=True, data=str(ctx.user_id))
    monkeypatch.setattr(UserContextTool, 'execute', read)
    agent = FlowDeckAgent(None)
    with runtime.sessions() as db:
        graph = agent._get_graph(make_user_lc_tools(1, db))
        assert graph is agent._get_graph(make_user_lc_tools(2, db))
        for user_id in (1, 2, 1):
            config = {'configurable': {'execution_context': ExecutionContext(user_id=user_id, db=db, max_tool_calls=3)}}
            graph.nodes['tool_node'].bound.invoke({'messages': [AIMessage(content='', tool_calls=[
                {'name': 'get_user_context', 'args': {}, 'id': 'read'},
                {'name': 'update_user_memory', 'args': {'memory_note': f'private-{user_id}'}, 'id': 'write'},
            ])]}, config)
        assert identities == [1, 2, 1]
        db.expire_all()
        assert 'private-2' not in db.query(UserProfile).filter_by(user_id=1).one().ai_memory_text
        assert 'private-1' not in db.query(UserProfile).filter_by(user_id=2).one().ai_memory_text

    def overlap(user_id):
        with runtime.sessions() as db:
            ctx = ExecutionContext(user_id=user_id, db=db, max_tool_calls=2)
            return graph.nodes['tool_node'].bound.invoke({'messages': [AIMessage(content='', tool_calls=[
                {'name': 'get_user_context', 'args': {}, 'id': 'read'},
                {'name': 'update_user_memory', 'args': {'memory_note': f'overlap-{user_id}'}, 'id': 'write'},
            ])]}, {'configurable': {'execution_context': ctx}})
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(overlap, (1, 2)))
    for user_id, response in zip((1, 2), responses):
        assert response['messages'][0].content == str(user_id)
    with runtime.sessions() as db:
        assert 'overlap-2' not in db.query(UserProfile).filter_by(user_id=1).one().ai_memory_text
        assert 'overlap-1' not in db.query(UserProfile).filter_by(user_id=2).one().ai_memory_text


def test_parallel_tool_calls_share_one_hard_budget(runtime, monkeypatch):
    from ai_engine.agent.graph import FlowDeckAgent
    from ai_engine.agent.lc_tools import make_user_lc_tools
    from ai_engine.agent.tool import ExecutionContext, ToolResult
    from ai_engine.agent.tools.user_context import UserContextTool
    from langchain_core.messages import AIMessage
    calls = Mock(return_value=ToolResult(ok=True, data='ok'))
    monkeypatch.setattr(UserContextTool, 'execute', calls)
    with runtime.sessions() as db:
        ctx = ExecutionContext(user_id=1, db=db, max_tool_calls=1)
        graph = FlowDeckAgent(None)._get_graph(make_user_lc_tools(1, db))
        result = graph.nodes['tool_node'].bound.invoke({'messages': [AIMessage(content='', tool_calls=[
            {'name': 'get_user_context', 'args': {}, 'id': str(i)} for i in range(3)
        ])]}, {'configurable': {'execution_context': ctx}})
        assert calls.call_count == result['tool_calls_made'] == 1
        assert sum('TOOL_BUDGET_EXCEEDED' in m.content for m in result['messages']) == 2


def test_python_tool_cannot_read_or_write_host_sentinel(tmp_path):
    from ai_engine.agent.tools.execute_python import _run_sandboxed
    sentinel = tmp_path / 'sentinel'
    sentinel.write_text('private')
    assert 'TOOL_DISABLED' in _run_sandboxed(f"import io; print(io.FileIO({str(sentinel)!r}, 'r').read())")
    _run_sandboxed(f"import io; io.FileIO({str(sentinel)!r}, 'w').write(b'changed')")
    assert sentinel.read_text() == 'private'


def test_oauth_requires_matching_unexpired_single_use_state(runtime, monkeypatch):
    from routers import users
    app = FastAPI()
    app.include_router(users.router)
    def get_db():
        with runtime.sessions() as db:
            yield db
    app.dependency_overrides[database.get_db] = get_db
    monkeypatch.setattr(users, 'GOOGLE_CLIENT_ID', 'test')
    monkeypatch.setattr(users, 'GOOGLE_REDIRECT_URI', 'http://testserver/api/auth/google/callback')
    callback = Mock(return_value=(SimpleNamespace(email='test@example.invalid', id=1), 'test-jwt', False))
    monkeypatch.setattr(users, 'auth_google_callback', callback)
    client = TestClient(app)
    from urllib.parse import urlparse, parse_qs
    start = client.get('/api/auth/google', follow_redirects=False)
    state = parse_qs(urlparse(start.headers['location']).query)['state'][0]
    # A matching cookie alone must not authorize an expired nonce.
    with runtime.sessions() as db:
        db.query(OAuthState).update({'expires_at': datetime.utcnow() - timedelta(seconds=1)})
        db.commit()
    client.get('/api/auth/google/callback', params={'code': 'test', 'state': state}, follow_redirects=False)
    assert callback.call_count == 0
    start = client.get('/api/auth/google', follow_redirects=False)
    state = parse_qs(urlparse(start.headers['location']).query)['state'][0]
    client.get('/api/auth/google/callback', params={'code': 'test', 'state': 'wrong'}, follow_redirects=False)
    assert callback.call_count == 0
    client.get('/api/auth/google/callback', params={'code': 'test', 'state': state}, follow_redirects=False)
    assert callback.call_count == 1
    client.cookies.set('flowdeck-oauth-state', state)
    client.get('/api/auth/google/callback', params={'code': 'test', 'state': state}, follow_redirects=False)
    assert callback.call_count == 1


@pytest.mark.parametrize('secret', ['', 'short', 'flowdeck-dev-secret-change-in-production', 'your-secret-key-change-in-production'])
def test_insecure_signing_configuration_is_rejected(monkeypatch, secret):
    import auth
    monkeypatch.setattr(auth, 'JWT_SECRET', secret)
    with pytest.raises(RuntimeError):
        auth.validate_auth_configuration()


def test_payment_capture_is_reconciled_once_after_credit_failure(runtime, monkeypatch):
    from services import paypal_service as service
    with runtime.sessions() as db:
        subject = db.get(User, 1).auth_subject
        amount = SimpleNamespace(total='5.00', currency='USD')
        payment = SimpleNamespace(id='PAY-review', state='approved', transactions=[SimpleNamespace(
            custom=f'{subject}:starter:500', amount=amount,
            related_resources=[SimpleNamespace(sale=SimpleNamespace(id='SALE-review', state='completed', amount=amount))])])
        payment.execute = Mock(side_effect=AssertionError('Must not recapture'))
        monkeypatch.setattr(service.paypalrestsdk.Payment, 'find', lambda _id: payment)
        real = token_service.record_transaction
        monkeypatch.setattr(token_service, 'record_transaction', lambda *a, **kw: None)
        with pytest.raises(RuntimeError):
            service.execute_payment(payment.id, 'payer', db, user_id=1)
        assert db.get(PaymentOrder, payment.id).status == 'captured'
        monkeypatch.setattr(token_service, 'record_transaction', real)
        assert service.execute_payment(payment.id, 'payer', db, user_id=1)['tokens_credited'] == 500
        assert service.execute_payment(payment.id, 'payer', db, user_id=1)['success']
        assert db.query(Usage).filter_by(transaction_type='purchase').count() == 1
        with pytest.raises(ValueError):
            service.execute_payment(payment.id, 'payer', db, user_id=2)


def test_chat_cannot_report_uncommitted_or_excess_charges(runtime, monkeypatch):
    from services.chat_turn_service import ChatTurnService
    from models.db_models import ChatReservation
    service = ChatTurnService()
    with runtime.sessions() as db:
        token_service.record_transaction(1, 1, 'initial_balance', db)
    turn_id, session_id, _ = service.prepare_turn(user_id=1, session_id=None, body_messages=[{'role': 'user', 'content': 'hello'}])
    with runtime.sessions() as db:
        assert token_service.get_balance_from_ledger(1, db) == 0
        with pytest.raises(RuntimeError):
            service._complete_turn(db=db, turn_id=turn_id, session_id=session_id, user_id=1,
                content='reply', tokens_used=20001, model_metadata=None, tools_called=0,
                tool_calls=[], skill_events=[], charts=[], follow_up_questions=[])
        service._fail_turn(db, turn_id, 'excess usage')
        service._fail_turn(db, turn_id, 'retry')
        assert db.query(Usage).filter_by(transaction_type='chat_cost').count() == 0
        assert token_service.get_balance_from_ledger(1, db) == 1
        assert db.get(ChatReservation, turn_id).settled


def test_restart_recovers_paid_analysis_and_chat_reservations(runtime):
    from services.execution_recovery import recover_interrupted_work
    from services.chat_turn_service import ChatTurnService
    with runtime.sessions() as db:
        token_service.record_transaction(1, 1000, 'initial_balance', db)
        ok, run_id = token_service.deduct_for_analysis(1, 'TEST', db)
        assert ok
    turn_id, _, _ = ChatTurnService().prepare_turn(user_id=1, session_id=None, body_messages=[{'role': 'user', 'content': 'hello'}])
    recover_interrupted_work()
    recover_interrupted_work()
    with runtime.sessions() as db:
        assert db.get(Execution, run_id).status == db.get(ChatTurn, turn_id).status == 'failed'
        assert token_service.get_balance_from_ledger(1, db) == 1000
        assert db.query(Usage).filter_by(transaction_type='refund').count() == 1


def test_multi_history_accepts_vendor_format_and_includes_end_date(monkeypatch):
    from ai_engine.agent.tools.multi_market_data import _fetch_multi_historical_prices
    from ai_engine.tradingagents.datasources import info_service_client as client
    monkeypatch.setattr(client, 'require_info_service', lambda: None)
    fetch = Mock(return_value='# Stock data\n# Total records: 2\n# Retrieved today\n\nDate,Close\n2026-01-01,100\n2026-01-02,110\n')
    monkeypatch.setattr(client, 'get_ticker_data', fetch)
    result = json.loads(_fetch_multi_historical_prices(['TEST'], '2026-01-01', '2026-01-02'))
    assert result['tickers_fetched'] == ['TEST']
    assert '2026-01-02,110' in result['data']['TEST']
    assert fetch.call_args.args[-1] == '2026-01-03'


def test_period_return_uses_previous_session_close():
    from ai_engine.agent.skills.compare_stocks import _compute_returns
    data = json.dumps({'data': {'TEST': 'Date,Close\n2025-12-30,80\n2025-12-31,100\n2026-01-02,105\n2026-01-05,110\n'}})
    result = _compute_returns(data, ['TEST'], '2026-01-01', '2026-01-05')
    assert result[0]['return_pct'] == 10


def test_negative_event_probability_is_not_bullish():
    from services.polymarket_service import PolymarketService
    result = PolymarketService()._aggregate_sentiment([
        {'question': 'Will TEST crash 50%?', 'outcomePrices': ['0.9', '0.1'], 'volume': 1000000, 'relevance_score': 1}], [])
    assert result['trend'] == 'unknown'
    assert result['overall_sentiment'] is result['confidence'] is None


def test_missing_etf_inputs_are_unavailable(monkeypatch):
    from ai_engine.tradingagents.agents.utils import valuation_tools as v
    monkeypatch.setattr(v, '_get_current_risk_free_rate', lambda: 0.04)
    monkeypatch.setattr(v, '_get_market_risk_premium', lambda: 0.05)
    result = v._build_index_etf_valuation(ticker='TEST', current_price=100, fundamentals={'QuoteType': 'ETF'})
    assert result['valuation_available'] is False
    assert result['fair_value_base'] is None
    assert result['valuation_conviction'] == 'UNAVAILABLE'


@pytest.mark.parametrize('override', [
    {'backend_url': 'https://untrusted.invalid'}, {'shallow_thinker': 'unapproved-model'},
    {'deep_thinker': 'unapproved-model'}, {'llm_provider': 'anthropic'},
    {'research_depth': 0}, {'research_depth': 6}, {'research_depth': True},
    {'analysts': []}, {'analysts': ['unknown']},
])
def test_public_analysis_policy_rejects_overrides_before_vendors_or_charges(runtime, monkeypatch, override):
    import asyncio
    from fastapi import HTTPException
    from routers import analyses
    monkeypatch.setenv('LLM_PROVIDER', 'azure')
    gateway = Mock(side_effect=AssertionError('Must validate before vendor access'))
    monkeypatch.setattr(analyses, 'get_data_gateway', gateway)
    monkeypatch.setattr(analyses.app_services, 'get_analysis_service', lambda: Mock())
    request = Mock()
    async def body():
        return {'ticker': 'TEST', **override}
    request.json = body
    with runtime.sessions() as db:
        with pytest.raises(HTTPException) as error:
            asyncio.run(analyses.start_analysis(request, db.get(User, 1), db))
        assert error.value.status_code == 422
        assert db.query(Usage).count() == db.query(Execution).count() == 0
        gateway.assert_not_called()


def test_llm_budget_is_shared_and_rejects_before_provider_invocation():
    from ai_engine.agent.llm_budget import BudgetedLLM, LLMBudgetExceeded
    from langchain_core.messages import HumanMessage
    provider = Mock()
    provider.bind_tools.return_value = provider
    provider.bind.return_value = provider
    budget = BudgetedLLM(provider, 7000)
    budget.invoke([HumanMessage(content='hello')])
    with pytest.raises(LLMBudgetExceeded):
        budget.bind_tools([]).invoke([HumanMessage(content='hello again')])
    assert provider.invoke.call_count == 1
    assert provider.bind.call_args.kwargs['max_tokens'] <= 4096


def test_google_budget_retains_provider_output_limit_when_tools_are_bound():
    from ai_engine.agent.llm_budget import BudgetedLLM
    class GoogleModel:
        __module__ = 'langchain_google_genai.chat_models'
        def bind_tools(self, tools):
            return bound
    bound = Mock()
    BudgetedLLM(GoogleModel(), 10000).bind_tools([]).invoke(['hello'])
    assert bound.bind.call_args.kwargs == {'max_output_tokens': 4096}


def test_entity_ids_and_ledger_operations_survive_deletion(runtime):
    with runtime.sessions() as db:
        token_service.record_transaction(1, 1000, 'initial_balance', db)
        ok, old_id = token_service.deduct_for_analysis(1, 'OLD', db)
        assert ok
        token_service.refund_for_execution(1, old_id, db)
        ok, new_id = token_service.deduct_for_analysis(1, 'NEW', db)
        assert ok and new_id > old_id
        assert token_service.get_balance_from_ledger(1, db) == 800
        assert db.query(Usage).filter_by(transaction_type='analysis_cost').count() == 2
        # Legacy deleted IDs are still present only in the polymorphic ledger.
        db.add(Usage(user_id=1, amount=0, balance_after=800, transaction_type='chat_cost',
                     related_entity_type='chat_message', related_entity_id=4000))
        session = ChatSession(user_id=1)
        db.add(session)
        db.flush()
        message = ChatMessage(session_id=session.id, role='user', content='new')
        db.add(message)
        db.commit()
        assert message.id > 4000
        db.delete(message)
        db.commit()
        next_message = ChatMessage(session_id=session.id, role='user', content='next')
        db.add(next_message)
        db.commit()
        assert next_message.id > message.id


def test_each_distinct_viewer_is_rewarded_once(runtime):
    with runtime.sessions() as db:
        db.add(User(id=3, email='third@example.invalid'))
        db.commit()
        token_service.record_transaction(1, 1000, 'initial_balance', db)
        run = token_service.record_analysis_run(1, 'TEST', db)
        assert token_service.record_view(run, 2, db)
        assert token_service.record_view(run, 3, db)
        assert not token_service.record_view(run, 2, db)
        assert token_service.get_balance_from_ledger(1, db) == 1002
        assert db.get(Execution, run).earned_tokens == 2


def test_chat_settlement_is_atomic_and_terminal_and_prevents_active_deletion(runtime):
    from services.chat_turn_service import ChatTurnService, ChatTurnConflict
    from services.chat_persistence import delete_session_for_user
    service = ChatTurnService()
    turn_id, session_id, _ = service.prepare_turn(user_id=1, session_id=None,
        body_messages=[{'role': 'user', 'content': 'hello'}])
    with pytest.raises(ChatTurnConflict):
        service.prepare_turn(user_id=1, session_id=session_id,
            body_messages=[{'role': 'user', 'content': 'overlap'}])
    with runtime.sessions() as db:
        with pytest.raises(ValueError):
            delete_session_for_user(db, session_id, 1)
        db.rollback()
        result = service._complete_turn(db=db, turn_id=turn_id, session_id=session_id, user_id=1,
            content='reply', tokens_used=10001, model_metadata=None, tools_called=0,
            tool_calls=[], skill_events=[], charts=[], follow_up_questions=[])
        assert result['type'] == 'done' and result['platform_tokens_used'] == 2
        assert result['balance'] == 998
        service._fail_turn(db, turn_id, 'late failure must not change success')
        assert db.get(ChatTurn, turn_id).status == 'completed'
        assert db.query(Usage).filter_by(transaction_type='chat_release').count() == 1
        assert token_service.get_balance_from_ledger(1, db) == 998
        assert delete_session_for_user(db, session_id, 1)


def test_sse_worker_starts_even_without_consuming_response(runtime, monkeypatch):
    import asyncio
    from routers import chat
    service = Mock()
    service.prepare_turn.return_value = (1, 2, [{'role': 'user', 'content': 'hello'}])
    monkeypatch.setattr(chat, 'get_chat_turn_service', lambda: service)
    with runtime.sessions() as db:
        response = asyncio.run(chat.chat_stream(chat.ChatRequest(messages=[{'role': 'user', 'content': 'hello'}]),
                                               db.get(User, 1), db))
        assert response.media_type == 'text/event-stream'
        service.subscribe.assert_called_once_with(1)
        service.run_turn_async.assert_called_once()


def test_completed_analysis_status_ignores_stale_live_cache(runtime):
    from services.analysis_service import AnalysisService
    from services.data_cache import set_analysis_status
    with runtime.sessions() as db:
        run_id = token_service.record_analysis_run(1, 'TEST', db)
        db.get(Execution, run_id).status = 'completed'
        db.commit()
    set_analysis_status('ticker', run_id, {'status': 'running'})
    service = AnalysisService()
    assert service.get_analysis_status(run_id)['status'] == 'completed'
    service._fail_analysis(run_id, 'late cache failure')
    with runtime.sessions() as db:
        assert db.get(Execution, run_id).status == 'completed'


def test_unpaid_failed_digest_does_not_create_a_refund(runtime):
    with runtime.sessions() as db:
        run_id = token_service.record_execution(1, 'daily_digest', 'user_date', 'test', db)
        db.get(Execution, run_id).status = 'failed'
        db.commit()
        assert not token_service.refund_for_failed_digest(run_id, db)
        assert db.query(Usage).count() == 0


def test_runtime_lock_rejects_another_owner(runtime):
    from services.runtime_lock import acquire_runtime_lock
    lock = acquire_runtime_lock(runtime.engine)
    try:
        with pytest.raises(RuntimeError, match='Another Flowdeck process'):
            acquire_runtime_lock(runtime.engine)
    finally:
        lock.close()
    acquire_runtime_lock(runtime.engine).close()


@pytest.mark.parametrize('streaming', [False, True])
def test_full_chat_capacity_releases_reservation_without_provider_call(runtime, monkeypatch, streaming):
    from services import chat_turn_service
    service = chat_turn_service.ChatTurnService()
    provider = Mock(side_effect=AssertionError('Capacity rejection must not invoke a provider'))
    monkeypatch.setattr(chat_turn_service, 'get_chat_service', provider)
    turn_id, session_id, history = service.prepare_turn(user_id=1, session_id=None,
        body_messages=[{'role': 'user', 'content': 'hello'}])
    for _ in range(8):
        assert service._slots.acquire(blocking=False)
    run = service.run_turn_async if streaming else service.run_turn_sync
    run(turn_id=turn_id, session_id=session_id, user_id=1, messages=history, context=None)
    with runtime.sessions() as db:
        assert db.get(ChatTurn, turn_id).status == 'failed'
        assert token_service.get_balance_from_ledger(1, db) == 1000
    provider.assert_not_called()
    service._workers.shutdown(wait=True)


def test_etf_sensitivity_uses_nullable_schema(monkeypatch):
    from ai_engine.tradingagents.agents.utils import valuation_tools as v
    from ai_engine.tradingagents.agents.analysts.valuation_analyst import ValuationSensitivity
    monkeypatch.setattr(v, '_get_current_risk_free_rate', lambda: 0.04)
    monkeypatch.setattr(v, '_get_market_risk_premium', lambda: 0.05)
    result = v._build_index_etf_valuation(ticker='TEST', current_price=100,
        fundamentals={'QuoteType': 'ETF', 'ForwardPE': 20})
    assert result['fair_value_base'] is not None
    assert result['valuation_conviction'] == 'low'
    assert all(value is None for value in ValuationSensitivity(**result['valuation_sensitivity']).model_dump().values())


def test_full_legacy_schema_upgrade_preserves_data_and_seeds_deleted_ids(tmp_path):
    from sqlalchemy import MetaData
    from schema_migrations import migrate
    legacy = MetaData()
    additions = {'users': 'auth_subject', 'api_keys': 'user_subject', 'usage': 'operation_key'}
    new_tables = {'entity_sequences', 'oauth_states', 'payment_orders', 'chat_reservations', 'analysis_jobs'}
    for source in database.Base.metadata.sorted_tables:
        if source.name in new_tables:
            continue
        table = source.to_metadata(legacy)
        removed = additions.get(table.name)
        if removed:
            for constraint in list(table.constraints):
                if removed in constraint.columns:
                    table.constraints.remove(constraint)
            for index in list(table.indexes):
                if removed in index.columns:
                    table.indexes.remove(index)
            table._columns.remove(table.c[removed])
    engine = create_engine(f"sqlite:///{tmp_path / 'full-legacy.sqlite'}")
    legacy.create_all(engine)
    with engine.begin() as conn:
        conn.execute(legacy.tables['users'].insert().values(id=50, email='legacy@example.invalid'))
        conn.execute(legacy.tables['chat_sessions'].insert().values(id=70, user_id=50))
        conn.execute(legacy.tables['chat_messages'].insert().values(id=90, session_id=70, role='user', content='preserved'))
        conn.execute(legacy.tables['usage'].insert().values(user_id=50, amount=123, balance_after=123, transaction_type='initial_balance'))
        # Genuine orphan left by old FK-disabled connections.
        conn.execute(legacy.tables['chat_sessions'].insert().values(id=71, user_id=999))
    engine.dispose()
    event.listen(engine, 'connect', database._set_sqlite_pragmas)
    database.Base.metadata.create_all(engine)
    migrate(engine)
    migrate(engine)
    with sessionmaker(bind=engine)() as db:
        assert db.get(ChatMessage, 90).content == 'preserved'
        assert db.get(ChatSession, 71) is None
        assert token_service.get_balance_from_ledger(50, db) == 123
        assert len(db.get(User, 50).auth_subject) >= 32
        db.delete(db.get(User, 50))
        db.commit()
        assert db.query(ChatMessage).count() == 0
        replacement = User(email='replacement@example.invalid')
        db.add(replacement)
        db.commit()
        assert replacement.id > 50
    engine.dispose()
