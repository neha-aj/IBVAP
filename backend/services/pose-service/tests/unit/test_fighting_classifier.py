from app.inference.fighting_classifier import select_closest_pair
from app.schemas.pose import PoseReading


def _reading(x: float, y: float) -> PoseReading:
    return PoseReading(x=x, y=y, posture="standing", confidence=0.9)


def test_no_pair_when_fewer_than_two_people() -> None:
    assert select_closest_pair([], proximity_threshold=12.0) is None
    assert select_closest_pair([_reading(50, 50)], proximity_threshold=12.0) is None


def test_no_pair_when_nobody_close_enough() -> None:
    readings = [_reading(10, 10), _reading(90, 90)]
    assert select_closest_pair(readings, proximity_threshold=12.0) is None


def test_pair_found_and_sorted_left_to_right() -> None:
    readings = [_reading(60, 50), _reading(55, 50)]  # index 0 is to the right of index 1
    pair = select_closest_pair(readings, proximity_threshold=12.0)
    assert pair == (1, 0)


def test_picks_the_closest_of_several_candidates() -> None:
    readings = [_reading(10, 10), _reading(50, 50), _reading(52, 50), _reading(90, 90)]
    pair = select_closest_pair(readings, proximity_threshold=12.0)
    assert pair == (1, 2)
