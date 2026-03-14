from core.ingestion.pdf_reader import extract_text_from_pdf


def test_pdf_extraction():

    pdf_path = "sample_exam.pdf"

    text = extract_text_from_pdf(pdf_path)

    print("\n--- Extracted Text Preview ---\n")
    print(text[:1000])

    assert isinstance(text, str)
    assert len(text) > 0