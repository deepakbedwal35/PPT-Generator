import io
import json
import os
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import app


class ValidationTests(unittest.TestCase):
    def test_frame_count_retry(self):
        source = (app.PUBLIC / 'sample.tex').read_text()
        wrong_count = source.replace('\\end{document}', '\\begin{frame}{Extra}Extra\\end{frame}\\end{document}')
        with patch('app.generate_latex_once', side_effect=[wrong_count, source]) as generate:
            self.assertEqual(app.generate_latex('Test', 3), source)
            self.assertEqual(generate.call_count, 2)
        with patch('app.generate_latex_once', return_value=wrong_count):
            with self.assertRaisesRegex(app.AppError, 'instead of 3'):
                app.generate_latex('Test', 3)

    @patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'})
    def test_transient_provider_retry(self):
        source = (app.PUBLIC / 'sample.tex').read_text()
        response = {'candidates': [{'content': {'parts': [{'text': source}]}}]}
        error = urllib.error.HTTPError('https://example.com', 503, 'unavailable', {}, None)
        with patch('app.urllib.request.urlopen', side_effect=[error, io.BytesIO(json.dumps(response).encode())]) as request:
            with patch('app.time.sleep'):
                self.assertEqual(app.generate_latex('Test', 3), source.strip())
            self.assertEqual(request.call_count, 2)

    def test_fenced_document_and_incomplete_source(self):
        source = (app.PUBLIC / 'sample.tex').read_text()
        self.assertEqual(app.beamer_source('```latex\n' + source + '\n```'), source.strip())
        for invalid in (None, '', r'\documentclass{article}\begin{document}x\end{document}'):
            with self.assertRaises(app.AppError):
                app.beamer_source(invalid)

    def test_invalid_pdf_and_png(self):
        for value in (b'', b'not pdf'):
            with self.assertRaises(app.AppError):
                app.ensure_pdf(value)
        for value in (b'', b'\x89PNG\r\n\x1a\n' + bytes(16)):
            with self.assertRaises(app.AppError):
                app.png_dimensions(value)

    @patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'})
    def test_generation_excludes_thoughts(self):
        source = (app.PUBLIC / 'sample.tex').read_text()
        response = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
            {'thought': True, 'text': 'internal text'}, {'text': source}]}}]}
        with patch('app.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())):
            self.assertEqual(app.generate_latex('Test', 3), source.strip())
        for count in (True, 2, 13, '3'):
            with self.assertRaises(app.AppError):
                app.generate_latex('Test', count)

    @patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'})
    def test_generation_reports_truncation_and_quota(self):
        response = {'candidates': [{'finishReason': 'MAX_TOKENS'}]}
        with patch('app.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())):
            with self.assertRaisesRegex(app.AppError, 'MAX_TOKENS'):
                app.generate_latex('Test', 3)
        error = urllib.error.HTTPError('https://example.com', 429, 'quota', {}, None)
        with patch('app.urllib.request.urlopen', side_effect=error):
            with self.assertRaisesRegex(app.AppError, 'quota'):
                app.generate_latex('Test', 3)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_config_and_static_isolation(self):
        with urllib.request.urlopen(self.url + '/api/config') as response:
            config = json.load(response)
            self.assertNotIn('GEMINI_API_KEY', config)
        for path in ('/.env', '/app.py', '/api/missing', '/../.env'):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()

    def test_bad_requests_and_cross_origin(self):
        cases = [(b'{', 'application/json', {}, 400),
                 (b'[]', 'application/json', {}, 400),
                 (b'{}', 'text/plain', {}, 415),
                 (b'{}', 'application/json', {'Origin': 'https://example.com'}, 403)]
        for data, kind, headers, status in cases:
            request = urllib.request.Request(self.url + '/api/compile', data=data,
                                             headers={'Content-Type': kind, **headers})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, status)
            self.assertIn('error', json.load(error.exception))
            error.exception.close()


if __name__ == '__main__':
    unittest.main()
