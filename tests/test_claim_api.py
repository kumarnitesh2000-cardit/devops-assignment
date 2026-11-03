import asyncio
import unittest
from io import BytesIO

from fastapi import HTTPException, UploadFile
from pypdf import PdfWriter

from claims_pipeline.main import process_pdf_claim


def make_blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class ClaimApiTests(unittest.TestCase):
    def test_rejects_non_pdf_upload(self):
        upload = UploadFile(filename="claim.pdf", file=BytesIO(b"not a PDF"))
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(process_pdf_claim(claim_id="claim-1", file=upload))
        self.assertEqual(raised.exception.status_code, 415)

    def test_rejects_pdf_without_extractable_text(self):
        upload = UploadFile(filename="scan.pdf", file=BytesIO(make_blank_pdf()))
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(process_pdf_claim(claim_id="claim-2", file=upload))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("OCR", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()