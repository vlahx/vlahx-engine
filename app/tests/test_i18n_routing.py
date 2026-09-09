from __future__ import annotations
import unittest
from starlette.requests import Request
from app.core.i18n import (
    extract_locale_and_path,
    build_locale_url,
    resolve_locale,
    get_supported_locales,
)

class TestI18nRouting(unittest.TestCase):

    def test_extract_locale_and_path(self):
        loc, path = extract_locale_and_path("/ro/blog/test-post")
        self.assertEqual(loc, "ro")
        self.assertEqual(path, "/blog/test-post")

        loc_en, path_en = extract_locale_and_path("/en/category/tech")
        self.assertEqual(loc_en, "en")
        self.assertEqual(path_en, "/category/tech")

        loc_none, path_none = extract_locale_and_path("/blog/test-post")
        self.assertIsNone(loc_none)
        self.assertEqual(path_none, "/blog/test-post")

        loc_exempt, path_exempt = extract_locale_and_path("/admin/plugins")
        self.assertIsNone(loc_exempt)
        self.assertEqual(path_exempt, "/admin/plugins")

    def test_build_locale_url(self):
        self.assertEqual(build_locale_url("/blog/post", "ro"), "/ro/blog/post")
        self.assertEqual(build_locale_url("/ro/blog/post", "en"), "/en/blog/post")
        self.assertEqual(build_locale_url("/", "en"), "/en")
        self.assertEqual(build_locale_url("/admin/login", "ro"), "/admin/login")
        self.assertEqual(build_locale_url("https://vlahx.org/blog/post", "ro"), "https://vlahx.org/ro/blog/post")

    def test_resolve_locale(self):
        req1 = Request({"type": "http", "method": "GET", "path": "/ro/blog/post", "headers": [], "query_string": b""})
        self.assertEqual(resolve_locale(req1), "ro")

        req2 = Request({"type": "http", "method": "GET", "path": "/blog/post", "headers": [], "query_string": b"lang=en"})
        self.assertEqual(resolve_locale(req2), "en")

if __name__ == "__main__":
    unittest.main()
