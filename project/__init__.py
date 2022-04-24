import hmac
import hashlib

import time

import requests  # type: ignore
import os
import base64
from flask import Flask, request, json, jsonify


app = Flask(__name__, static_url_path="/static", static_folder="web/static")

app_url = os.environ["APP_URL"]
readme_url = app_url + "/static/README.md"
policy_url = app_url + "/static/restrict.json"


@app.route("/", methods=["GET", "POST"])
def hello_world():
    """endpoint for availability check"""
    if request.method == "GET":
        app.logger.info("received request")
        return "<p>Hello, World!</p>"
    if request.method == "POST":
        return "<p>Hello, Post-World!</p>"


def create_initial_commit(base_query_url, headers, branchname):
    """create README for first commit

    Parameters
    ----------
    base_query_url: str
    headers: dict[str, str]
        headers for GitHub API request, must include auth token and accepted content type
    branchname: str
        name of branch where commit should be created

    Returns
    ------
    str
        full qualified url of pointing to created commit
    """
    content = {}
    content["branch"] = branchname
    content["message"] = "This is a placeholder for security purposes"
    app.logger.info(f"loading readme from {readme_url}")
    readme_request = requests.get(readme_url)
    base64_bytes = base64.b64encode(readme_request.content)
    content["content"] = base64_bytes.decode("utf-8")
    blob_request = requests.put(
        base_query_url + "/contents/README.md",
        headers=headers,
        data=json.dumps(content),
    )

    app.logger.log(10, blob_request.request.body)
    app.logger.log(10, blob_request.request.headers)
    app.logger.log(10, blob_request.content)
    blob_sha = blob_request.json()["commit"]["tree"]["sha"]
    commit_sha = blob_request.json()["commit"]["sha"]
    commit_html_url = blob_request.json()["commit"]["html_url"]
    app.logger.log(10, f"blob_request.status_code: {blob_request.status_code}")

    app.logger.log(10, f"blob_sha: {blob_sha}")
    app.logger.log(10, f"commit_sha: {commit_sha}")
    commit_data = {}
    commit_data["message"] = "initial commit"
    commit_data["tree"] = blob_sha
    commit_request = requests.post(
        base_query_url + "/git/commits", headers=headers, data=json.dumps(commit_data)
    )
    app.logger.log(10, commit_request.content)
    app.logger.log(10, f"commit_request.status_code: {commit_request.status_code}")

    p_commit_data = {}
    p_commit_data["force"] = True
    p_commit_request = requests.post(
        base_query_url + "", headers=headers, data=json.dumps(p_commit_data)
    )
    app.logger.log(10, p_commit_request.content)
    app.logger.log(10, f"p_commit_request.status_code: {p_commit_request.status_code}")
    return commit_html_url


def restrict_commits(base_query_url, headers, branch_name):
    """create branch protection

    Parameters
    ----------
    base_query_url: str
    headers: dict[str, str]
        headers for GitHub API request, must include auth token and accepted content type
    branch_name: str
        name of branch which should be protected
    """
    req_url = base_query_url + f"/branches/{branch_name}/protection"
    app.logger.log(10, req_url)
    app.logger.info(f"loading policy from {policy_url}")
    policy_def = requests.get(policy_url)
    parsed = json.loads(policy_def.content.decode("utf8"))
    restrict_request = requests.put(req_url, headers=headers, data=json.dumps(parsed))
    app.logger.log(10, restrict_request.content)
    app.logger.log(10, f"restrict_request.status_code: {restrict_request.status_code}")


def create_issue(base_query_url, headers, commit_url):
    """create an issue with the policy content and a mention

    Parameters
    ----------
    base_query_url: str
    headers: dict[str, str]
        headers for GitHub API request, must include auth token and accepted content type
    commit_url: str
        full qualified url pointing to the previously created commit
    """
    data = {}
    data["title"] = "Created branch protection rule"
    policy_def = requests.get(policy_url)
    parsed = json.loads(policy_def.content.decode("utf8"))
    app.logger.log(10, json.dumps(parsed, indent=4, sort_keys=True))
    data["body"] = (
        "@"
        + os.getenv("GITHUB_OWNER")
        + "\r\n"
        + "A protection rule for default branch has been created based on the following definition"
        + "\r\n"
        + "\r\n```\r\n"
        + json.dumps(parsed, indent=4, sort_keys=True)
        + "\r\n```\r\n"
        + "Please see the documentation for a definition of the different options. - "
        + "[Update branch protection](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection)"
    )
    if commit_url is not None:
        data["body"] += (
            "\r\nThe following commit has been automatically created for this: "
            + commit_url
        )
    req_url = base_query_url + f"/issues"
    app.logger.log(10, req_url)
    issue_request = requests.post(req_url, headers=headers, data=json.dumps(data))
    app.logger.log(10, issue_request.content)
    app.logger.log(10, issue_request.status_code)


def validate_signature(request):
    key = os.getenv("GITHUB_SECRET")
    key = bytes(key, "utf-8")
    expected_signature = hmac.new(
        key=key, msg=request.data, digestmod=hashlib.sha1
    ).hexdigest()
    incoming_signature = (
        request.headers.get("X-Hub-Signature").split("sha1=")[-1].strip()
    )
    return hmac.compare_digest(incoming_signature, expected_signature)


@app.route("/hooktest", methods=["POST"])
def hook_root():
    # validate signature
    sig_check_result = validate_signature(request)

    if (
        not sig_check_result
        # debug check for local debugging
        and not app.debug
    ):
        response = jsonify({"message": "Wrong secret"})
        app.logger.warn("authentication failed")
        return response, 401
    else:
        app.logger.info("passed signature verification")

    app.logger.log(10, f'X-Github-Event: {request.headers["X-Github-Event"]}')
    if request.headers["Content-Type"] == "application/json":
        payload = request.json
        if (
            request.headers["X-Github-Event"] == "repository"
            and payload["action"] == "created"
        ):
            app.logger.log(10, "now do the magic - created")
            token = os.getenv("GITHUB_TOKEN")
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }
            repo_name = payload["repository"]["full_name"]
            # default_branch_name = payload["repository"]["default_branch"]
            # hard-coded to 'main' because the payload for 'created' includes 'master' as 'default_branch'
            # even though default branch is set to 'main' in organization settings.
            default_branch_name = "main"
            base_query_url = f"https://api.github.com/repos/{repo_name}"
            r = requests.get(base_query_url + "/commits", headers=headers)
            app.logger.log(10, "default_branch:" + default_branch_name)
            app.logger.log(10, r.status_code)
            # only create initial commit if repository has not been initialized with content, e.g. README.md
            commit_url = None
            if r.status_code == 409:
                commit_url = create_initial_commit(
                    base_query_url, headers, default_branch_name
                )
            # restrict commits
            restrict_commits(base_query_url, headers, default_branch_name)
            # create issue with policy content and mention
            create_issue(base_query_url, headers, commit_url)

        response = jsonify({"message": "Success"})
        return response, 200

    else:
        response = jsonify({"message": "Unexpected Content-Type"})
        app.logger.warn("received request with wrong Content-Type")
        # unsupported media type
        return response, 415
