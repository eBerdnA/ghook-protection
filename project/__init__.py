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

POLICY_PATH = os.path.join(os.path.dirname(__file__), "web/static/restrict.json")
CODEOWNERS_PATH = os.path.join(os.path.dirname(__file__), "web/static/CODEOWNERS")


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
    readme_path = os.path.join(os.path.dirname(__file__), "web/static/README.md")
    with open(readme_path, "rb") as f:
        base64_bytes = base64.b64encode(f.read())
    content = {
        "branch": branchname,
        "message": "This is a placeholder for security purposes",
        "content": base64_bytes.decode("utf-8"),
    }
    blob_request = requests.put(
        base_query_url + "/contents/README.md",
        headers=headers,
        json=content,
    )

    app.logger.info(f"create file status: {blob_request.status_code}")
    app.logger.info(f"create file response: {blob_request.text}")
    if blob_request.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create initial commit: {blob_request.status_code} {blob_request.text}"
        )
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
        base_query_url + "/git/commits", headers=headers, json=commit_data
    )
    app.logger.log(10, commit_request.content)
    app.logger.log(10, f"commit_request.status_code: {commit_request.status_code}")

    p_commit_data = {}
    p_commit_data["force"] = True
    p_commit_request = requests.post(
        base_query_url + "", headers=headers, json=p_commit_data
    )
    app.logger.log(10, p_commit_request.content)
    app.logger.log(10, f"p_commit_request.status_code: {p_commit_request.status_code}")
    return commit_html_url


def create_codeowners(base_query_url, headers, branch_name):
    """upload CODEOWNERS file to the new repository

    Parameters
    ----------
    base_query_url: str
    headers: dict[str, str]
        headers for GitHub API request, must include auth token and accepted content type
    branch_name: str
        name of branch where file should be uploaded

    Returns
    ------
    None
    """
    app.logger.info(f"creating CODEOWNERS for {base_query_url}")
    with open(CODEOWNERS_PATH, "r") as f:
        template = f.read()

    owner = os.getenv("GITHUB_OWNER")
    content_str = template.replace("<OWNER>", owner)
    base64_bytes = base64.b64encode(content_str.encode("utf-8"))

    content = {
        "branch": branch_name,
        "message": "Add CODEOWNERS",
        "content": base64_bytes.decode("utf-8"),
    }

    req_url = base_query_url + "/contents/.github/CODEOWNERS"
    app.logger.log(10, f"PUT {req_url}")

    blob_request = requests.put(
        req_url,
        headers=headers,
        json=content,
    )

    app.logger.log(10, f"create codeowners status: {blob_request.status_code}")
    app.logger.log(10, f"create codeowners response: {blob_request.text}")

    if blob_request.status_code == 422:
        app.logger.warning(f"CODEOWNERS already exists, skipping")
        return

    if blob_request.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create CODEOWNERS: {blob_request.status_code} {blob_request.text}"
        )


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
    with open(POLICY_PATH) as f:
        parsed = json.load(f)
    restrict_request = requests.put(req_url, headers=headers, json=parsed)
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
    with open(POLICY_PATH) as f:
        parsed = json.load(f)
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
        + "A CODEOWNERS file has also been created with @"
        + os.getenv("GITHUB_OWNER")
        + " as the default owner."
        + "\r\n"
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
    issue_request = requests.post(req_url, headers=headers, json=data)
    app.logger.log(10, issue_request.content)
    app.logger.log(10, issue_request.status_code)


def validate_signature(request):
    key = bytes(os.getenv("GITHUB_SECRET"), "utf-8")
    expected_signature = hmac.new(
        key=key, msg=request.data, digestmod=hashlib.sha256
    ).hexdigest()
    incoming_signature = request.headers.get("X-Hub-Signature-256", "")
    incoming_signature = incoming_signature.split("sha256=")[-1].strip()
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
                "Accept": "application/vnd.github+json",
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
            # create CODEOWNERS
            create_codeowners(base_query_url, headers, default_branch_name)
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
