from app.workers.rag_ingestion_worker import process_queued_jobs


def main() -> None:
    processed = process_queued_jobs()
    print(f"Processed {processed} queued ingestion job(s).")


if __name__ == "__main__":
    main()
