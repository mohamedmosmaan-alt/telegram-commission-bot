import json

from app.services import customer_service
from app.services.customer_service import LookupResult
from tests.conftest import insert_agent, insert_commission


def test_valid_registered_phone_is_found():
    insert_agent("1153420", "محمود عبد الحي علي", "+201000255551", agency_name="ساندى")

    result, matches = customer_service.verify_phone(999, "+201000255551")

    assert result == LookupResult.FOUND_UNIQUE
    assert len(matches) == 1
    assert matches[0].master == "1153420"
    assert matches[0].agent_name == "محمود عبد الحي علي"


def test_unregistered_phone_returns_not_found_and_discloses_nothing():
    insert_agent("1153420", "محمود عبد الحي علي", "+201000255551")

    result, matches = customer_service.verify_phone(999, "+201099999999")

    assert result == LookupResult.NOT_FOUND
    assert matches == []


def test_session_survives_data_change_on_next_sync():
    insert_agent("1153420", "محمود عبد الحي علي", "+201000255551")
    insert_commission("1153420", json.dumps({"Master": "1153420", "Rep": "Mohammed.A.Hammad"}))

    _, matches = customer_service.verify_phone(999, "+201000255551")
    customer_service.create_session(999, matches[0])

    fields = customer_service.get_commission_fields(customer_service.get_session(999).master)
    assert fields["Rep"] == "Mohammed.A.Hammad"

    # simulate the sheet changing on the next sync: same master, new Rep
    from app.database.db import get_connection
    with get_connection() as conn:
        conn.execute(
            "UPDATE commission_reports SET fields_json = ? WHERE master = ?",
            (json.dumps({"Master": "1153420", "Rep": "Ahmed.New.Rep"}), "1153420"),
        )

    fields_after = customer_service.get_commission_fields(customer_service.get_session(999).master)
    assert fields_after["Rep"] == "Ahmed.New.Rep"


def test_a_different_telegram_user_cannot_see_someone_elses_session():
    insert_agent("1153420", "محمود عبد الحي علي", "+201000255551")
    _, matches = customer_service.verify_phone(111, "+201000255551")
    customer_service.create_session(111, matches[0])

    assert customer_service.get_session(111) is not None
    assert customer_service.get_session(222) is None


def test_missing_commission_report_is_handled_gracefully():
    insert_agent("9999999", "Some Agent", "+201099998888")
    _, matches = customer_service.verify_phone(999, "+201099998888")
    assert customer_service.get_commission_fields(matches[0].master) is None
