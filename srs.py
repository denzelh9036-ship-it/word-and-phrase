from datetime import date, timedelta


INTERVALS = [0, 1, 2, 4, 7, 15]

STAGE_NAMES = {
    0: "New",
    1: "Learned",
    2: "Review 1",
    3: "Review 2",
    4: "Review 3",
    5: "Mastered",
}


def stage_name(stage):
    return STAGE_NAMES.get(stage, f"Stage {stage}")


def _next_date(stage, today=None):
    today = today or date.today()
    days = INTERVALS[min(stage, len(INTERVALS) - 1)]
    return (today + timedelta(days=days)).isoformat()


def on_correct(stage, today=None):
    new_stage = min(stage + 1, 5)
    return new_stage, _next_date(new_stage, today)


def on_wrong(stage, today=None):
    new_stage = max(stage - 1, 0)
    today = today or date.today()
    return new_stage, today.isoformat()
