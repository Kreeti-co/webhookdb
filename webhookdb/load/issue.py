# coding=utf-8
from __future__ import unicode_literals, print_function

from flask import request, jsonify, url_for
from flask_login import current_user
import bugsnag
from . import load
from webhookdb.tasks.issue import (
    sync_issue, spawn_page_tasks_for_issues
)
from webhookdb.exceptions import NotFound


@load.route('/repos/<owner>/<repo>/issues/<int:number>', methods=["POST"])
def issue(owner, repo, number):
    """
    Load a single issue from Github into WebhookDB.

    :query children: scan all children objects. Defaults to ``false``
    :query inline: process the request inline instead of creating a task
      on the task queue. Defaults to ``false``. Ignored if ``children``
      is true.
    :statuscode 200: issue successfully loaded inline
    :statuscode 202: task successfully queued
    :statuscode 404: specified issue was not found on Github
    """
    children = bool(request.args.get("children", False))
    inline = bool(request.args.get("inline", False))
    bugsnag_ctx = {
        "owner": owner, "repo": repo, "number": number,
        "inline": inline, "children": children,
    }
    bugsnag.configure_request(meta_data=bugsnag_ctx)

    if inline and not children:
        try:
            sync_issue(
                owner, repo, number, children=False,
                requestor_id=current_user.get_id(),
            )
        except NotFound as exc:
            return jsonify({"message": exc.message}), 404
        else:
            return jsonify({"message": "success"})
    else:
        result = sync_issue.delay(
            owner, repo, number, children=children,
            requestor_id=current_user.get_id(),
        )
        resp = jsonify({"message": "queued"})
        resp.status_code = 202
        resp.headers["Location"] = url_for("tasks.status", task_id=result.id)
        return resp

@load.route('/repos/<owner>/<repo>/issues', methods=["POST"])
def issues(owner, repo):
    """
    Queue tasks to load all issues on a single Github repository
    into WebhookDB.

    :query children: scan all children objects. Defaults to ``false``
    :query state: one of ``all``, ``open``, or ``closed``. This parameter
      is proxied to the `Github API for listing issues`_.
    :statuscode 202: task successfully queued

    .. _Github API for listing issues: https://developer.github.com/v3/issues/#list-issues-for-a-repository
    """
    bugsnag_ctx = {"owner": owner, "repo": repo}
    bugsnag.configure_request(meta_data=bugsnag_ctx)
    state = request.args.get("state", "open")
    children = bool(request.args.get("children", False))

    result = spawn_page_tasks_for_issues.delay(
        owner, repo, state, children=children,
        requestor_id=current_user.get_id(),
    )
    resp = jsonify({"message": "queued"})
    resp.status_code = 202
    resp.headers["Location"] = url_for("tasks.status", task_id=result.id)
    return resp
