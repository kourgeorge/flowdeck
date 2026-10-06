"""Ordered additive migrations for the supported SQLite deployment.

Run by init_db before serving traffic. Back up the database before upgrading.
Legacy numeric JWTs are intentionally invalidated; legacy API keys are revoked.
"""
import secrets
from sqlalchemy import inspect, text


def migrate(engine):
    if engine.dialect.name != "sqlite":
        raise RuntimeError("Schema upgrades currently support SQLite only")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY)")
        # Seed before orphan cleanup or the first post-upgrade deletion. Retain
        # these high-water marks even if every row in an entity table is deleted.
        for table in ('users', 'executions', 'chat_sessions', 'chat_messages', 'chat_turns'):
            conn.execute(text(f'''
                INSERT INTO entity_sequences(name, last_id)
                VALUES (:name, COALESCE((SELECT MAX(id) FROM "{table}"), 0))
                ON CONFLICT(name) DO UPDATE SET last_id=MAX(last_id, excluded.last_id)
            '''), {'name': table})
        if conn.execute(text("SELECT 1 FROM schema_versions WHERE version=1")).scalar():
            return
        columns = {table: {c['name'] for c in inspect(conn).get_columns(table)}
                   for table in ('users', 'api_keys', 'usage')}
        if 'auth_subject' not in columns['users']:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN auth_subject VARCHAR(64)")
        for (user_id,) in conn.execute(text("SELECT id FROM users WHERE auth_subject IS NULL")):
            conn.execute(text("UPDATE users SET auth_subject=:subject WHERE id=:id"),
                         {'subject': secrets.token_urlsafe(32), 'id': user_id})
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_auth_subject ON users(auth_subject)")
        if 'user_subject' not in columns['api_keys']:
            conn.exec_driver_sql("ALTER TABLE api_keys ADD COLUMN user_subject VARCHAR(64)")
        # Unbound legacy keys cannot be safely attributed after historical ID reuse.
        conn.exec_driver_sql("UPDATE api_keys SET is_active=0 WHERE user_subject IS NULL")
        if 'operation_key' not in columns['usage']:
            conn.exec_driver_sql("ALTER TABLE usage ADD COLUMN operation_key VARCHAR(255)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS uq_usage_operation_key ON usage(operation_key)")
        # Purge truly orphaned records left by old connections without FK enforcement.
        # Parent deletion cascades to their dependents now that enforcement is enabled.
        from database import Base
        for table in reversed(Base.metadata.sorted_tables):
            for fk in table.foreign_keys:
                parent = fk.column.table.name
                column = fk.parent.name
                predicate = f'"{column}" IS NOT NULL AND "{column}" NOT IN (SELECT "{fk.column.name}" FROM "{parent}")'
                if fk.ondelete == 'SET NULL':
                    conn.exec_driver_sql(f'UPDATE "{table.name}" SET "{column}"=NULL WHERE {predicate}')
                else:
                    conn.exec_driver_sql(f'DELETE FROM "{table.name}" WHERE {predicate}')
        conn.exec_driver_sql("INSERT INTO schema_versions(version) VALUES (1)")
