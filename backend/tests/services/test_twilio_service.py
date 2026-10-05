from unittest.mock import MagicMock

import pytest
from twilio.base.exceptions import TwilioRestException

from app.services import twilio_service


@pytest.fixture(autouse=True)
def _fake_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(twilio_service, "_get_client", lambda: client)
    return client


def test_owned_twilio_number_is_valid(_fake_client):
    _fake_client.incoming_phone_numbers.list.return_value = [MagicMock()]

    is_valid, reason = twilio_service.is_valid_caller_id("+15551234567")

    assert is_valid is True
    assert reason == ""
    _fake_client.outgoing_caller_ids.list.assert_not_called()


def test_verified_outgoing_caller_id_is_valid(_fake_client):
    _fake_client.incoming_phone_numbers.list.return_value = []
    _fake_client.outgoing_caller_ids.list.return_value = [MagicMock()]

    is_valid, reason = twilio_service.is_valid_caller_id("+15551234567")

    assert is_valid is True
    assert reason == ""


def test_unknown_number_is_rejected(_fake_client):
    _fake_client.incoming_phone_numbers.list.return_value = []
    _fake_client.outgoing_caller_ids.list.return_value = []

    is_valid, reason = twilio_service.is_valid_caller_id("+15551234567")

    assert is_valid is False
    assert "isn't a Twilio number" in reason


def test_twilio_api_failure_propagates(_fake_client):
    _fake_client.incoming_phone_numbers.list.side_effect = TwilioRestException(
        status=401, uri="/IncomingPhoneNumbers", msg="Authenticate"
    )

    with pytest.raises(TwilioRestException):
        twilio_service.is_valid_caller_id("+15551234567")
