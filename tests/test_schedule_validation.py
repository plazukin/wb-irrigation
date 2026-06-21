from types import SimpleNamespace

from irrigationd.domain.schedule_validation import find_schedule_overlap


def schedule(
    schedule_id=1, days="0", start="06:00", duration=600, enabled=True,
):
    return SimpleNamespace(
        id=schedule_id, days_of_week=days, start_time=start,
        duration_sec=duration, enabled=enabled,
    )


def test_rejects_overlapping_schedule() -> None:
    existing = schedule()
    assert find_schedule_overlap(
        "0", "06:05", 600, True, [existing]
    ) is existing


def test_allows_adjacent_schedule() -> None:
    assert find_schedule_overlap(
        "0", "06:10", 600, True, [schedule()]
    ) is None


def test_detects_overlap_across_week_boundary() -> None:
    existing = schedule(days="6", start="23:55", duration=600)
    assert find_schedule_overlap(
        "0", "00:00", 300, True, [existing]
    ) is existing


def test_ignores_disabled_and_updated_schedule() -> None:
    existing = schedule(enabled=False)
    assert find_schedule_overlap("0", "06:00", 600, True, [existing]) is None
    existing.enabled = True
    assert find_schedule_overlap(
        "0", "06:00", 600, True, [existing], exclude_id=1
    ) is None
