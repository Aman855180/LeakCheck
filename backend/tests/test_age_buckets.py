import pytest
from app.services.recon_engine import get_age_bucket


def test_age_bucket_boundary_days():
    """
    Test exact boundary thresholds for standardized age buckets:
    - 0 to 7 days: '0-7'
    - 8 to 15 days: '8-15'
    - 16 to 30 days: '16-30'
    - 31+ days: '31+'
    """
    # Day 0
    assert get_age_bucket(0) == "0-7"
    # Day 6
    assert get_age_bucket(6) == "0-7"
    # Day 7 (Boundary upper of 0-7)
    assert get_age_bucket(7) == "0-7"

    # Day 8 (Boundary lower of 8-15)
    assert get_age_bucket(8) == "8-15"
    # Day 14
    assert get_age_bucket(14) == "8-15"
    # Day 15 (Boundary upper of 8-15)
    assert get_age_bucket(15) == "8-15"

    # Day 16 (Boundary lower of 16-30)
    assert get_age_bucket(16) == "16-30"
    # Day 29
    assert get_age_bucket(29) == "16-30"
    # Day 30 (Boundary upper of 16-30)
    assert get_age_bucket(30) == "16-30"

    # Day 31 (Boundary lower of 31+)
    assert get_age_bucket(31) == "31+"
    # Day 45
    assert get_age_bucket(45) == "31+"
    # Day 90
    assert get_age_bucket(90) == "31+"
