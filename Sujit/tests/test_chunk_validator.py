from app.services.chunk_validator import ChunkValidator


def test_validator_keeps_unique_chunks_within_word_limits() -> None:
    validator = ChunkValidator(min_words=2, max_words=4)
    chunks = [
        {"text": "one two"},
        {"text": "one two"},
        {"text": "one two three four five"},
    ]

    valid, report = validator.validate(chunks)

    assert valid == [{"text": "one two"}]
    assert report == {
        "total_chunks": 3,
        "valid_chunks": 1,
        "empty_chunks": 0,
        "small_chunks": 0,
        "large_chunks": 1,
        "duplicate_chunks": 1,
    }


def test_validator_rejects_empty_and_short_chunks() -> None:
    validator = ChunkValidator(min_words=2, max_words=4)

    valid, report = validator.validate([{"text": "  "}, {"text": "one"}])

    assert valid == []
    assert report["empty_chunks"] == 1
    assert report["small_chunks"] == 1
