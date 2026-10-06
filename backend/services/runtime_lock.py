"""Enforce the supported one-process SQLite runtime before crash recovery."""
from pathlib import Path


def acquire_runtime_lock(engine):
    import fcntl
    if engine.dialect.name != 'sqlite' or not engine.url.database or engine.url.database == ':memory:':
        raise RuntimeError('The server requires a persistent SQLite database and one worker')
    path = Path(engine.url.database).resolve().with_suffix('.runtime.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('Another Flowdeck process owns this database. Use one worker/replica.')
    return handle
