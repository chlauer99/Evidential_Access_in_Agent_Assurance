"""Offline regression tests for record-access pagination and URL boundaries."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mab_harness"))
from fhir_urls import resolve_fhir_url

BASE = "http://localhost:8080/fhir/"


class FhirUrlTests(unittest.TestCase):
    def test_pagination_root_without_trailing_slash(self):
        url = "http://localhost:8080/fhir?_getpages=abc&_getpagesoffset=20&_count=20"
        self.assertEqual(resolve_fhir_url(url, BASE), url)

    def test_resource_and_relative_urls(self):
        for reference, expected in [
            ("Observation?code=K", BASE + "Observation?code=K"),
            ("/fhir/Patient?family=Smith", BASE + "Patient?family=Smith"),
            ("/fhir?_getpages=abc", "http://localhost:8080/fhir?_getpages=abc"),
            ("?_getpages=abc", BASE + "?_getpages=abc"),
            (BASE, BASE),
        ]:
            with self.subTest(reference=reference):
                self.assertEqual(resolve_fhir_url(reference, BASE), expected)

    def test_foreign_origins_and_paths_rejected(self):
        for url in [
            "http://evil.example/fhir/Observation", "//evil.example/fhir/",
            "http://localhost:8081/fhir/Patient", "https://localhost:8080/fhir/",
            "http://localhost:8080/fhir-other", "/admin", "../admin",
            "/fhir/%2e%2e/admin", "/fhir/%2e%2e%2fadmin",
            "http://user@localhost:8080/fhir/", "http://localhost:8080@evil.example/fhir/",
            "file:///fhir/Patient", BASE + "Patient#fragment", BASE + "Patient\n",
            BASE + "%5c..%5cadmin", "http://localhost:bad/fhir/",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                resolve_fhir_url(url, BASE)


if __name__ == "__main__":
    unittest.main()
