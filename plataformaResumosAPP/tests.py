import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from .topdf import to_pdf
from .views import TemporaryFileResponse


class PdfGenerationTests(SimpleTestCase):
    def test_to_pdf_uses_output_directory_and_timeout(self):
        with tempfile.TemporaryDirectory() as output_dir:
            def create_pdf(command, **kwargs):
                Path(command[-1]).with_suffix('.pdf').write_bytes(b'%PDF')

            with patch('plataformaResumosAPP.topdf.subprocess.run', side_effect=create_pdf) as run:
                pdf_path = to_pdf({'document_type': 'resumo'}, output_dir)

            self.assertEqual(os.path.dirname(pdf_path), output_dir)
            self.assertEqual(Path(pdf_path).read_bytes(), b'%PDF')
            self.assertEqual(run.call_args.kwargs['timeout'], 60)

    def test_to_pdf_reports_timeout(self):
        with tempfile.TemporaryDirectory() as output_dir:
            with patch(
                'plataformaResumosAPP.topdf.subprocess.run',
                side_effect=subprocess.TimeoutExpired('pdflatex', 60),
            ):
                with self.assertRaisesRegex(RuntimeError, 'excedeu o limite de 60 segundos'):
                    to_pdf({'document_type': 'resumo'}, output_dir)

    def test_temporary_file_response_cleans_directory_when_closed(self):
        temporary_directory = tempfile.TemporaryDirectory()
        pdf_path = Path(temporary_directory.name) / 'caderno.pdf'
        pdf_path.write_bytes(b'%PDF')

        response = TemporaryFileResponse(
            open(pdf_path, 'rb'),
            temporary_directory,
            as_attachment=True,
        )
        response.close()

        self.assertFalse(os.path.exists(temporary_directory.name))
