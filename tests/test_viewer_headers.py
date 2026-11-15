"""The local viewer's same-origin policy covers success and error responses."""
import http.client
import contextlib
import io
import socket
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

    def test_access_logs_omit_request_targets(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.check_response('GET', '/?private-test-token=fictional-secret', 200)
            self.check_response('GET', '/fictional-private-filename?token=secret', 404)
        logs = output.getvalue()
        self.assertIn('Response 200', logs)
        self.assertIn('Response 404', logs)
        self.assertNotIn('fictional', logs)
        self.assertNotIn('token', logs)
        self.assertNotIn('secret', logs)

    def test_malformed_request_logs_omit_raw_request(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            with socket.create_connection(self.server.server_address) as connection:
                connection.sendall(b'GET /fictional-secret HTTP/not-a-version\r\n\r\n')
                while connection.recv(4096):
                    pass
        logs = output.getvalue()
        self.assertIn('Request error', logs)
        self.assertNotIn('fictional-secret', logs)
        self.assertNotIn('not-a-version', logs)
