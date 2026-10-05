from datetime import datetime, timedelta

from app.domain.calls.follow_up import parse_follow_up_date, suggest_reschedule


def test_parse_follow_up_date_empty_defaults_to_three_days():
    result = parse_follow_up_date("")
    expected = datetime.utcnow() + timedelta(days=3)
    assert abs((result - expected).total_seconds()) < 5


def test_parse_follow_up_date_today():
    result = parse_follow_up_date("Today would work")
    assert abs((result - datetime.utcnow()).total_seconds()) < 5


def test_parse_follow_up_date_tomorrow():
    result = parse_follow_up_date("Let's talk tomorrow")
    expected = datetime.utcnow() + timedelta(days=1)
    assert abs((result - expected).total_seconds()) < 5


def test_parse_follow_up_date_in_n_days():
    result = parse_follow_up_date("in 5 days")
    expected = datetime.utcnow() + timedelta(days=5)
    assert abs((result - expected).total_seconds()) < 5


def test_parse_follow_up_date_in_n_weeks():
    result = parse_follow_up_date("in 2 weeks")
    expected = datetime.utcnow() + timedelta(weeks=2)
    assert abs((result - expected).total_seconds()) < 5


def test_parse_follow_up_date_next_week():
    result = parse_follow_up_date("next week sounds good")
    expected = datetime.utcnow() + timedelta(days=7)
    assert abs((result - expected).total_seconds()) < 5


def test_parse_follow_up_date_next_month():
    result = parse_follow_up_date("next month")
    expected = datetime.utcnow() + timedelta(days=30)
    assert abs((result - expected).total_seconds()) < 5


def test_parse_follow_up_date_bare_number_of_days():
    result = parse_follow_up_date("call back 10 days from now")
    expected = datetime.utcnow() + timedelta(days=10)
    assert abs((result - expected).total_seconds()) < 5


def test_parse_follow_up_date_unrecognized_defaults_to_three_days():
    result = parse_follow_up_date("whenever is convenient")
    expected = datetime.utcnow() + timedelta(days=3)
    assert abs((result - expected).total_seconds()) < 5


def test_suggest_reschedule_on_a_weekday_gives_two_days_out():
    # Wednesday 2025-01-08 + 2 days = Friday, not a weekend
    now = datetime(2025, 1, 8)
    target, label = suggest_reschedule(now)
    assert target == now + timedelta(days=2)
    assert "in 2 days" in label


def test_suggest_reschedule_nudges_weekend_to_monday():
    # Thursday 2025-01-09 + 2 days = Saturday -> nudge to Monday
    now = datetime(2025, 1, 9)
    target, label = suggest_reschedule(now)
    assert target.weekday() == 0  # Monday
    assert "next Monday" in label


def test_suggest_reschedule_friday_lands_on_sunday_nudges_to_monday():
    # Friday 2025-01-10 + 2 days = Sunday -> nudge to Monday
    now = datetime(2025, 1, 10)
    target, label = suggest_reschedule(now)
    assert target.weekday() == 0  # Monday
    assert "next Monday" in label
