import logging
import sys


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s trace_id=%(trace_id)s span_id=%(span_id)s request_id=%(request_id)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
