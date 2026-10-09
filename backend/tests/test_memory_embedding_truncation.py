import tiktoken

from ai_engine.tradingagents.agents.utils import memory as memory_mod


def test_long_situation_is_truncated_before_embedding():
    enc = tiktoken.get_encoding("cl100k_base")
    long_text = "Revenue grew while cash burn increased. " * 3000
    assert len(enc.encode(long_text)) > 8192

    truncated = memory_mod._truncate_for_embedding(long_text)
    assert len(enc.encode(truncated)) <= memory_mod._EMBEDDING_MAX_TOKENS
    assert long_text.startswith(truncated)


def test_short_situation_is_unchanged():
    assert memory_mod._truncate_for_embedding("short report") == "short report"


def test_get_embedding_sends_truncated_input():
    sent = {}

    class FakeEmbeddings:
        def create(self, model, input):
            sent["input"] = input

            class R:
                data = [type("D", (), {"embedding": [0.1]})()]

            return R()

    mem = memory_mod.FinancialSituationMemory.__new__(memory_mod.FinancialSituationMemory)
    mem._local_embedder = None
    mem.embedding = "text-embedding-3-small"
    mem.client = type("C", (), {"embeddings": FakeEmbeddings()})()

    mem.get_embedding("word " * 20000)
    enc = tiktoken.get_encoding("cl100k_base")
    assert len(enc.encode(sent["input"])) <= memory_mod._EMBEDDING_MAX_TOKENS
