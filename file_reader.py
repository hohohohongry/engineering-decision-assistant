import pymupdf as fitz
import pandas as pd
from io import BytesIO


# PDF를 페이지별로 읽는 함수
def read_pdf(uploaded_file):

    file_bytes = uploaded_file.getvalue()

    pdf_document = fitz.open(
        stream=file_bytes,
        filetype="pdf"
    )

    pages = []

    for page_number, page in enumerate(pdf_document):

        text = page.get_text("text")

        pages.append({
            "file": uploaded_file.name,
            "page": page_number + 1,
            "text": text
        })

    pdf_document.close()

    return pages


# Excel을 시트별로 읽는 함수
def read_excel(uploaded_file):

    file_bytes = uploaded_file.getvalue()

    excel_file = pd.ExcelFile(
        BytesIO(file_bytes),
        engine="openpyxl"
    )

    sheets = []

    for sheet_name in excel_file.sheet_names:

        df = pd.read_excel(
            excel_file,
            sheet_name=sheet_name
        )

        sheets.append({
            "file": uploaded_file.name,
            "sheet": sheet_name,
            "data": df
        })

    return sheets
