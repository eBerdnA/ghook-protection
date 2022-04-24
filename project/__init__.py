import hmac
import hashlib

import time
import requests  # type: ignore
import os
import base64
from pprint import pprint
from flask import Flask, request, json, jsonify

app = Flask(__name__, static_url_path="/static", static_folder="web/static")

app_url = os.environ["APP_URL"]
readme_url = app_url + "/static/README.md"
policy_url = app_url + "/static/restrict.json"


@app.route("/", methods=["GET", "POST"])
def hello_world():
    if request.method == "GET":
        return "<p>Hello, World!</p>"
    if request.method == "POST":
        return "<p>Hello, Post-World!</p>"


def create_initial_commit(base_query_url, headers, branchname):
    # create README for first commit
    content = {}
    content["branch"] = branchname
    content["message"] = "This is a placeholder for security purposes"
    readme_request = requests.get(readme_url)
    base64_bytes = base64.b64encode(readme_request.content)
    content["content"] = base64_bytes.decode("utf-8")
    blob_request = requests.put(
        base_query_url + "/contents/README.md",
        headers=headers,
        data=json.dumps(content),
    )
    print(blob_request.request.body)
    print(blob_request.request.headers)
    print(blob_request.content)
    blob_sha = blob_request.json()["commit"]["tree"]["sha"]
    commit_sha = blob_request.json()["commit"]["sha"]
    commit_html_url = blob_request.json()["commit"]["html_url"]
    print(f"blob_request.status_code: {blob_request.status_code}")

    print(f"blob_sha: {blob_sha}")
    print(f"commit_sha: {commit_sha}")
    commit_data = {}
    commit_data["message"] = "initial commit"
    commit_data["tree"] = blob_sha
    commit_request = requests.post(
        base_query_url + "/git/commits", headers=headers, data=json.dumps(commit_data)
    )
    print(commit_request.content)
    print(f"commit_request.status_code: {commit_request.status_code}")

    p_commit_data = {}
    p_commit_data["force"] = True
    p_commit_request = requests.post(
        base_query_url + "", headers=headers, data=json.dumps(p_commit_data)
    )
    print(p_commit_request.content)
    print(f"p_commit_request.status_code: {p_commit_request.status_code}")
    return commit_html_url


def restrict_commits(base_query_url, headers, branch_name):
    req_url = base_query_url + f"/branches/{branch_name}/protection"
    print(req_url)
    policy_def = requests.get(policy_url)
    parsed = json.loads(policy_def.content.decode("utf8"))
    restrict_request = requests.put(req_url, headers=headers, data=json.dumps(parsed))
    print(restrict_request.content)
    print(f"restrict_request.status_code: {restrict_request.status_code}")
    return restrict_request.content


def create_issue(base_query_url, headers, commit_url):
    """create an issue with the policy content and a mention"""
    data = {}
    data["title"] = "Created branch protection rule"
    policy_def = requests.get(policy_url)
    parsed = json.loads(policy_def.content.decode("utf8"))
    print(json.dumps(parsed, indent=4, sort_keys=True))
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
        + "[Update branch protection](https://docs.github.com/en/rest/reference/branches#update-branch-protection)"
    )
    if commit_url is not None:
        data["body"] += (
            "\r\nThe following commit has been automatically created for this: "
            + commit_url
        )
    req_url = base_query_url + f"/issues"
    print(req_url)
    issue_request = requests.post(req_url, headers=headers, data=json.dumps(data))
    print(issue_request.content)
    print(issue_request.status_code)


def validate_signature(request):
    key = os.getenv("GITHUB_SIGNATURE")
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
        return response, 401
    else:
        print("passed signature verification")

    print(request.headers["X-Github-Event"])
    if request.headers["Content-Type"] == "application/json":  # calling json objects
        payload = request.json
        # print(json.dumps(request.json))
        if (
            request.headers["X-Github-Event"] == "repository"
            and payload["action"] == "created"
        ):
            print("now do the magic - created")
            token = os.getenv("GITHUB_TOKEN")
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }
            repo_name = payload["repository"]["full_name"]
            default_branch_name = payload["repository"]["default_branch"]
            base_query_url = f"https://api.github.com/repos/{repo_name}"
            r = requests.get(base_query_url + "/commits", headers=headers)
            pprint(r.json())
            print("default_branch:" + default_branch_name)
            if r.status_code == 409:
                commit_url = create_initial_commit(
                    base_query_url, headers, default_branch_name
                )
            # restrict commits
            content = restrict_commits(base_query_url, headers, default_branch_name)
            # create issue with policy content and mention
            create_issue(base_query_url, headers, commit_url)

        # return json.dumps(request.json)
        response = jsonify({"message": "Success"})
        return response, 200

    else:
        response = jsonify({"message": "Unexpected Content-Type"})
        # unsupported media type
        return response, 415
