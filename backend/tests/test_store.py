from __future__ import annotations

import pytest

from app.storage.store import MongoStore


class _Collection:
    def __init__(self) -> None:
        self.update = None

    async def find_one_and_update(self, query, update, **kwargs):
        self.update = update
        return {"_id": query["_id"]}


class _Mongo:
    def __init__(self) -> None:
        self.target = _Collection()

    def collection(self, name: str):
        return self.target


@pytest.mark.asyncio
async def test_mongo_increment_omits_conflicting_parent_default() -> None:
    mongo = _Mongo()
    store = MongoStore(mongo)  # type: ignore[arg-type]

    await store.increment(
        "user_profiles", "student", "prefs.intent_counts.process_guide", 1,
        {"user_id": "student", "role": "student", "prefs": {}, "feedback_counts": {}},
    )

    assert mongo.target.update == {
        "$inc": {"prefs.intent_counts.process_guide": 1},
        "$setOnInsert": {
            "user_id": "student", "role": "student", "feedback_counts": {},
        },
    }


@pytest.mark.asyncio
async def test_mongo_increment_keeps_non_overlapping_defaults() -> None:
    mongo = _Mongo()
    store = MongoStore(mongo)  # type: ignore[arg-type]

    await store.increment("user_profiles", "student", "query_count", 1, {"prefs": {}})

    assert mongo.target.update == {
        "$inc": {"query_count": 1},
        "$setOnInsert": {"prefs": {}},
    }
