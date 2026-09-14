"""Checking real PostgreSQL transactions in a disposable schema."""
from concurrent.futures import ThreadPoolExecutor
import os
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from beer_loss import storage
from test_core import packaging

@pytest.fixture
def postgres():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured.")
    schema = "beer_loss_test_" + uuid.uuid4().hex
    base = create_engine(url)
    with base.begin() as conn:
        conn.exec_driver_sql('CREATE SCHEMA "' + schema + '"')
    target = make_url(url).update_query_dict({"options": "-csearch_path=" + schema})
    engine = storage.make_engine(target.render_as_string(hide_password=False))
    yield engine
    engine.dispose()
    with base.begin() as conn:
        conn.exec_driver_sql('DROP SCHEMA "' + schema + '" CASCADE')
    base.dispose()

def test_postgres_shared_storage_concurrent_retry_and_history(postgres):
    request = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(lambda _: storage.save(postgres, packaging(), request), range(4)))
    assert sum(created for _, created in outcomes) == 1
    other = storage.make_engine(postgres.url.render_as_string(hide_password=False))
    original = storage.load(other)[0]
    assert original["id"] == outcomes[0][0]
    storage.void(other, original["id"], "QA reviewer", "Correcting quantity")
    assert storage.load(postgres) == []
    retained = storage.load(postgres, True)[0]
    assert retained["payload"]["volume_hl"] == 94
    assert retained["voided_by"] == "QA reviewer"
    storage.save(postgres, packaging())
    assert len(storage.load(other, True)) == 2
    other.dispose()
