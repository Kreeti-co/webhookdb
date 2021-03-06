# coding=utf-8
from __future__ import unicode_literals, print_function

from datetime import datetime
from . import load
from flask import jsonify
from flask_dance.contrib.github import github
from webhookdb.exceptions import RateLimited


@load.after_request
def attach_ratelimit_headers(response, gh_response=None):
    # A response with a non-OK response code is falsy, so can't just do:
    #   gh_response = gh_response or getattr(github, "last_response", None)
    # Instead, we have to actually check for None
    if gh_response is None:
        gh_response = getattr(github, "last_response", None)
    if gh_response is None:
        return response

    # attach ratelimit headers
    headers = ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset")
    for h in headers:
        if h in gh_response.headers:
            response.headers[h] = gh_response.headers[h]
    return response


@load.errorhandler(RateLimited)
def request_rate_limited(error):
    gh_resp = error.response
    try:
        upstream_msg = gh_resp.json()["message"]
    except Exception:
        upstream_msg = "Rate limited."

    wait_time = error.reset - datetime.now()
    sec = int(wait_time.total_seconds())
    wait_msg = "Try again in {sec} {unit}.".format(
        sec=sec, unit="second" if sec == 1 else "seconds",
    )

    msg = "{upstream} {wait}".format(
        upstream=upstream_msg,
        wait=wait_msg,
    )
    resp = jsonify({"error": msg})
    resp.status_code = 503
    return resp
