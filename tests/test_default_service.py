"""Regression tests for the shared default-service/corpus initialization.

The lazy initializers in ``src.llm.service`` were deadlocking: the non-reentrant
``_default_lock`` was acquired by ``get_default_service()`` and then re-acquired
by ``get_default_corpus()`` in the same thread, blocking the first-ever request
forever. These tests fail (time out) if the deadlock is reintroduced.
"""

import concurrent.futures

from src.llm import service as svc
from src.llm.service import QueryService
from tests.qa_helpers import build_fast_corpus


def _reset_defaults(monkeypatch):
    monkeypatch.setattr(svc, "build_default_corpus", build_fast_corpus)
    for name in ("_default_service", "_default_graph", "_default_store", "_default_embedding"):
        monkeypatch.setattr(svc, name, None)


def test_first_get_default_service_does_not_deadlock(monkeypatch):
    """The first-ever service build (Explain page) must return, not hang."""
    _reset_defaults(monkeypatch)

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(svc.get_default_service)
        service = future.result(timeout=15)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    assert isinstance(service, QueryService)
    assert svc.get_default_service() is service


def test_get_default_corpus_not_blocked_while_service_builds(monkeypatch):
    """A concurrent corpus load (upload path) must not block on the service build."""
    _reset_defaults(monkeypatch)

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    try:
        service_future = pool.submit(svc.get_default_service)
        corpus_future = pool.submit(svc.get_default_corpus)
        service = service_future.result(timeout=15)
        corpus = corpus_future.result(timeout=15)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    assert service is not None
    assert corpus[0] is not None
    assert svc._default_graph is corpus[0]
