"""The local viewer's same-origin policy covers success and error responses."""
import http.client
import threading
import unittest

from viewer.__main__ import PreviewServer


class ViewerHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = PreviewServer(("127.0.0.1", 0), 12)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def check_response(self, method, path, expected, **kwargs):
        connection = http.client.HTTPConnection(*self.server.server_address)
        try:
            connection.request(method, path, **kwargs)
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, expected)
            policy = response.getheader("Content-Security-Policy")
            for directive in ("default-src 'self'", "img-src 'self' data:",
                              "object-src 'none'", "base-uri 'none'",
                              "frame-ancestors 'none'", "form-action 'none'",
                              "worker-src 'none'"):
                self.assertIn(directive, policy.split('; '))
            self.assertNotIn('unsafe-inline', policy)
            self.assertNotIn('unsafe-eval', policy)
            self.assertEqual(response.getheader('X-Content-Type-Options'), 'nosniff')
            self.assertEqual(response.getheader('X-Frame-Options'), 'DENY')
            self.assertEqual(response.getheader('Referrer-Policy'),
                             'strict-origin-when-cross-origin')
            self.assertEqual(response.getheader('Permissions-Policy'),
                             'camera=(), microphone=(), geolocation=(), accelerometer=()')
        finally:
            connection.close()

    def test_successful_document_and_module(self):
        for path in ('/', '/index.html', '/viewer.js', '/style.css', '/api/catalog'):
            with self.subTest(path=path):
                self.check_response('GET', path, 200)

    def test_error_responses(self):
        self.check_response('GET', '/not-a-file', 404)
        self.check_response('POST', '/api/preview', 415, body='{}')
        self.check_response('POST', '/api/preview', 400, body='{',
                            headers={'Content-Type': 'application/json'})
