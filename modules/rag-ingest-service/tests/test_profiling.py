import logging
from time import sleep

from app.utils.profiling import clear_profile_events, get_profile_events, profile_step


def test_profile_step_reports_in_progress_and_done():
    logger = logging.getLogger("test_profile_step_reports_in_progress_and_done")
    clear_profile_events("job-1")

    with profile_step(True, logger, "job-1", "resource-1", "embedding_generation", chunk_count=2):
        running = get_profile_events("job-1")
        assert running[0]["step"] == "embedding_generation"
        assert running[0]["status"] == "IN_PROGRESS"
        assert running[0]["details"] == {"chunk_count": 2}
        sleep(0.001)

    completed = get_profile_events("job-1")
    assert completed[0]["status"] == "DONE"
    assert completed[0]["elapsed_ms"] > 0
    assert "_started_at" not in completed[0]
