from core.ingestion.pdf_reader import extract_text_from_pdf
from core.ingestion.question_parser import parse_questions


def test_question_parsing():

    text = extract_text_from_pdf("sample_exam.pdf")

    questions = parse_questions(text)

    print("\n--- Parsed Questions ---\n")

    for i, q in enumerate(questions):
        print(f"Q{i+1}:", q[:150], "\n")

    assert isinstance(questions, list)
    assert len(questions) > 0