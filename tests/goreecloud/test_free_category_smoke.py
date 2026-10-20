"""Offline, zero-network contracts for the NetBird-only category smoke checker."""
import importlib.util
import io
import json
from pathlib import Path
from urllib.parse import parse_qs
import unittest
from unittest.mock import patch

FILE=Path(__file__).resolve().parents[2] / "scripts" / "free_category_smoke.py"
spec=importlib.util.spec_from_file_location("free_category_smoke",FILE)
smoke=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=smoke
spec.loader.exec_module(smoke)


def document(test, results=None, failures=None):
    if results is None:
        results=[{"title":"Public learning resource","url":"https://example.org/education"}] * 6
    return json.dumps({
        "goreecloud":{"selected_engines":list(test.engines)},
        "results":results,
        "unresponsive_engines":failures if failures is not None else [],
    }).encode()


class Response(io.BytesIO):
    status=200


class FakeOpener:
    def __init__(self, response_factory=document):
        self.calls=[]
        self.response_factory=response_factory

    def open(self, request, timeout):
        self.calls.append((request,timeout))
        if request.full_url.endswith("/readyz"):
            return Response(b"READY")
        data=parse_qs(request.data.decode())
        category=next(x for x in smoke.CATEGORIES.values() if x.category_field in data)
        return Response(self.response_factory(category))


class CategorySmokeTests(unittest.TestCase):
    def test_all_four_default_categories_are_bounded_and_free(self):
        self.assertEqual({"general","images","videos","news"},set(smoke.CATEGORIES))
        self.assertEqual(("duckduckgo","bing","startpage"),smoke.CATEGORIES["general"].engines)
        self.assertEqual(("duckduckgo news",),smoke.CATEGORIES["news"].engines)
        self.assertTrue(all(len(c.engines)<=3 for c in smoke.CATEGORIES.values()))

    def test_request_is_post_with_query_only_in_body(self):
        for test in smoke.CATEGORIES.values():
            req=smoke.build_search_request(test)
            self.assertEqual(smoke.ORIGIN+"/search",req.full_url)
            self.assertEqual("POST",req.get_method())
            body=parse_qs(req.data.decode("ascii"))
            self.assertEqual(["1"],body[test.category_field])
            self.assertEqual([test.synthetic_query],body["q"])
            self.assertEqual([",".join(test.engines)],body["engines"])
            self.assertEqual(["json"],body["format"])
            self.assertNotIn("apikey",str(body).lower())
            self.assertNotIn("subscription",str(body).lower())
            self.assertNotIn("token",str(body).lower())
            self.assertFalse(req.has_header("Cookie"))

    def test_results_require_valid_metadata_and_actual_links(self):
        test=smoke.CATEGORIES["general"]
        self.assertEqual("results_observed",smoke.inspect_results(document(test),test)["state"])
        self.assertEqual(6,smoke.inspect_results(document(test),test)["result_links"])
        self.assertEqual(0,smoke.inspect_results(document(test),test)["unresponsive_engines"])

    def test_away_from_topic_news_is_not_reported_as_provider_outage(self):
        test=smoke.CATEGORIES["news"]
        outcome=smoke.inspect_results(document(test,results=[]),test)
        self.assertEqual("no_result_links",outcome["state"])
        self.assertEqual(0,outcome["unresponsive_engines"])

    def test_some_results_can_be_below_minimum(self):
        test=smoke.CATEGORIES["news"]
        outcome=smoke.inspect_results(document(test,results=[
            {"title":"NASA","url":"https://example.org/nasa"}]),test)
        self.assertEqual("below_minimum",outcome["state"])

    def test_invalid_or_non_public_http_destinations_never_count(self):
        test=smoke.CATEGORIES["images"]
        bad=[
            {"title":"Unsafe","url":"javascript:alert(1)"},
            {"title":"No network","url":"file:///etc/passwd"},
            {"title":"Relative","url":"/anything"},
            {"title":"","url":"https://example.org"},
            {"url":"https://example.org"},
            {"title":"Invalid","url":"http://user:password@example.org"},
            {"title":"Multiline","url":"https://example.org/a\nInjected"},
            {"title":"Loopback","url":"http://127.0.0.1/private"},
            {"title":"Metadata","url":"http://169.254.169.254/latest"},
            {"title":"Private IPv6","url":"http://[::1]:8080/admin"},
            {"title":"Local host","url":"http://localhost/path"},
            {"title":"Local domain","url":"http://machine.local/"},
            {"title":"Malformed IPv6","url":"https://[not-ipv6/path"},
        ]
        outcome=smoke.inspect_results(document(test,results=bad),test)
        self.assertEqual(0,outcome["result_links"])

    def test_wrong_selected_engine_never_passes(self):
        test=smoke.CATEGORIES["news"]
        bad=json.loads(document(test))
        bad["goreecloud"]["selected_engines"]=["brave.news"]
        with self.assertRaisesRegex(ValueError,"differ"):
            smoke.inspect_results(json.dumps(bad).encode(),test)

    def test_malformed_contract_rejected(self):
        test=smoke.CATEGORIES["general"]
        for raw in (b"invalid",b"null",b"[]",b"{}",b'{"results":[]}',b'{"goreecloud":{},"results":[],"unresponsive_engines":null}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                smoke.inspect_results(raw,test)

    def test_non_redirecting_handler(self):
        self.assertIsNone(smoke.NoRedirect().redirect_request(None,None,302,"Moved",{},smoke.ORIGIN+"/redirect"))

    def test_opener_never_follows_system_proxy_defaults(self):
        from urllib.request import ProxyHandler, HTTPSHandler
        handlers=smoke.client().handlers
        self.assertFalse(any(isinstance(x,ProxyHandler) for x in handlers))
        self.assertTrue(any(isinstance(x,HTTPSHandler) for x in handlers))
        self.assertTrue(any(isinstance(x,smoke.NoRedirect) for x in handlers))

    def test_one_readiness_and_one_request_per_category(self):
        opener=FakeOpener()
        with patch("builtins.print"):
            results,ok=smoke.run(tuple(smoke.CATEGORIES),opener=opener,nap=lambda _:None)
        self.assertTrue(ok)
        self.assertEqual(4,len(results))
        self.assertEqual(5,len(opener.calls))
        self.assertEqual(smoke.ORIGIN+"/readyz",opener.calls[0][0].full_url)
        self.assertTrue(all(r["state"]=="results_observed" for r in results))

    def test_news_empty_results_fail_check_without_claiming_a_network_error(self):
        opener=FakeOpener(response_factory=lambda category:document(category,results=[]))
        with patch("builtins.print"):
            records,ok=smoke.run(("news",),opener=opener,nap=lambda _:None)
        self.assertFalse(ok)
        self.assertEqual("no_result_links",records[0]["state"])

if __name__ == "__main__":
    unittest.main()
