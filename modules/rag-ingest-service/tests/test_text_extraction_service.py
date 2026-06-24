from app.services.text_extraction_service import TextExtractionService


def test_txt_extraction(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("hello world", encoding="utf-8")
    result = TextExtractionService().extract(path, ".txt")
    assert result.text == "hello world"
    assert result.parser_name == "plain_text"
