from app.services.text_extraction_service import TextExtractionService
from zipfile import ZipFile

from app.core.config import Settings
from app.services.file_metadata_service import FileMetadataService
from app.services.pdf_text_cleanup import PdfTextCleanupService


def test_txt_extraction(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("hello world", encoding="utf-8")
    result = TextExtractionService().extract(path, ".txt")
    assert result.text == "hello world"
    assert result.parser_name == "plain_text"


def test_epub_extraction(tmp_path):
    path = tmp_path / "sample.epub"
    write_sample_epub(path)

    result = TextExtractionService().extract(path, ".epub")
    assert result.parser_name == "epub-zip-html"
    assert "Green Card Guide" in result.text
    assert "Consular processing content." in result.text


def test_epub_metadata_extraction(tmp_path):
    path = tmp_path / "sample.epub"
    write_sample_epub(path)

    result = FileMetadataService().extract(path, ".epub")
    assert result.title == "EPUB Metadata Title"
    assert result.author == "EPUB Author"
    assert result.language == "en"
    assert result.publisher == "EPUB Publisher"


def test_pdf_cleanup_repairs_drop_caps_and_common_pdf_artifacts():
    text = (
        "[Page 1]\n"
        "Sons and Lovers\n"
        "Free eBooks at Planet eBook.com\n"
        "and email newsletter.\n"
        "M\n\n"
        "arley was dead: to begin with. There is no doubt what-\n"
        "ever about that. It was a mer- ry Christmas for gentle- men.\uf648\n\n"
        "[Page 2]\n"
        "2\n"
        "Sons and Lovers\n"
        "Free eBooks at Planet eBook.com\n"
        "The story continues andpresented the same problem.\n\n"
        "[Page 3]\n"
        "3\n"
        "Sons and Lovers\n"
        "Free eBooks at Planet eBook.com\n"
        "The ghost hadwarned him threequarters earlier."
    )

    cleaned, stats = PdfTextCleanupService(Settings()).clean(text)

    assert "Marley was dead" in cleaned
    assert "whatever about that" in cleaned
    assert "merry Christmas" in cleaned
    assert "gentlemen" in cleaned
    assert "Sons and Lovers" not in cleaned
    assert "Free eBooks at Planet eBook.com" not in cleaned
    assert "email newsletter" not in cleaned
    assert "\n2\n" not in cleaned
    assert "\n3\n" not in cleaned
    assert "and presented" in cleaned
    assert "had warned" in cleaned
    assert "three quarters" in cleaned
    assert "\uf648" not in cleaned
    assert stats.boilerplate_lines_removed == 4
    assert stats.page_number_lines_removed == 2
    assert stats.joined_word_repairs == 3


def write_sample_epub(path):
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
            <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
              <rootfiles>
                <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
              </rootfiles>
            </container>""",
        )
        archive.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0"?>
            <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
              <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                <dc:title>EPUB Metadata Title</dc:title>
                <dc:creator>EPUB Author</dc:creator>
                <dc:language>en</dc:language>
                <dc:publisher>EPUB Publisher</dc:publisher>
                <dc:date>2026-06-24</dc:date>
                <dc:description>EPUB metadata description.</dc:description>
              </metadata>
              <manifest>
                <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
              </manifest>
              <spine>
                <itemref idref="chapter1"/>
              </spine>
            </package>""",
        )
        archive.writestr(
            "OEBPS/chapter1.xhtml",
            """<html xmlns="http://www.w3.org/1999/xhtml">
              <body><h1>Green Card Guide</h1><p>Consular processing content.</p></body>
            </html>""",
        )
