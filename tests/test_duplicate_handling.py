from app.services import customer_service
from app.services.customer_service import LookupResult
from tests.conftest import insert_agent


def test_duplicate_phone_requires_secondary_verification():
    insert_agent("1000001", "Agent A", "+201012340000")
    insert_agent("1000002", "Agent B", "+201012340000")  # same phone, different Master

    result, matches = customer_service.verify_phone(999, "+201012340000")

    assert result == LookupResult.DUPLICATE
    assert len(matches) == 2


def test_duplicate_resolves_with_correct_master():
    insert_agent("1000001", "Agent A", "+201012340000")
    insert_agent("1000002", "Agent B", "+201012340000")

    agent = customer_service.resolve_duplicate(999, "+201012340000", "1000002")

    assert agent is not None
    assert agent.master == "1000002"
    assert agent.agent_name == "Agent B"


def test_duplicate_resolution_fails_with_wrong_master():
    insert_agent("1000001", "Agent A", "+201012340000")
    insert_agent("1000002", "Agent B", "+201012340000")

    agent = customer_service.resolve_duplicate(999, "+201012340000", "9999999")

    assert agent is None


def test_resolving_duplicate_never_leaks_the_other_agents_data():
    insert_agent("1000001", "Agent A", "+201012340000")
    insert_agent("1000002", "Agent B", "+201012340000")

    agent = customer_service.resolve_duplicate(999, "+201012340000", "1000002")
    assert agent.master != "1000001"
