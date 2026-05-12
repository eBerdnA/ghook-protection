import pytest
import json
import requests_mock as rm

def test_hooktest_wrong_secret(client, signed_request):
    # App is not in debug mode by default in our fixture
    response = signed_request("/hooktest", {"action": "created"}, "wrong-secret")
    assert response.status_code == 401
    assert response.get_json() == {"message": "Wrong secret"}

def test_hooktest_debug_mode_bypasses_sig(app, client):
    app.debug = True
    try:
        # Invalid signature
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid",
            "X-Github-Event": "repository"
        }
        response = client.post("/hooktest", data=json.dumps({"action": "not-created"}), headers=headers)
        assert response.status_code == 200
        assert response.get_json() == {"message": "Success"}
    finally:
        app.debug = False

def test_hooktest_wrong_content_type(client, raw_signed_request):
    body = b'{"action": "created"}'
    response = raw_signed_request("/hooktest", body, "test-secret", content_type="text/plain")
    assert response.status_code == 415
    assert response.get_json() == {"message": "Unexpected Content-Type"}

def test_hooktest_not_repository_event(client, signed_request):
    with rm.Mocker() as m:
        # Should not make any API calls
        response = signed_request("/hooktest", {"action": "created"}, "test-secret", event="push")
        assert response.status_code == 200
        assert response.get_json() == {"message": "Success"}
        assert not m.called

def test_hooktest_not_created_action(client, signed_request):
    with rm.Mocker() as m:
        # Should not make any API calls
        response = signed_request("/hooktest", {"action": "deleted"}, "test-secret", event="repository")
        assert response.status_code == 200
        assert response.get_json() == {"message": "Success"}
        assert not m.called

def test_hooktest_success_with_initial_commit(client, signed_request, mocker):
    payload = {
        "action": "created",
        "repository": {
            "full_name": "test-owner/test-repo",
            "default_branch": "main"
        }
    }
    
    with rm.Mocker() as m:
        # 1. Check commits -> return 409 (empty repo)
        m.get("https://api.github.com/repos/test-owner/test-repo/commits", status_code=409)
        
        # 2. Create initial commit
        m.put("https://api.github.com/repos/test-owner/test-repo/contents/README.md", 
              json={"commit": {"tree": {"sha": "tree-sha"}, "sha": "commit-sha", "html_url": "http://github.com/commit-url"}},
              status_code=201)
        
        # Dead code calls (slated for removal but still in code)
        m.post("https://api.github.com/repos/test-owner/test-repo/git/commits", status_code=201, json={})
        m.post("https://api.github.com/repos/test-owner/test-repo", status_code=200, json={})

        # 3. Create CODEOWNERS
        m.put("https://api.github.com/repos/test-owner/test-repo/contents/.github/CODEOWNERS",
              status_code=201, json={})

        # 4. Restrict commits
        m.put("https://api.github.com/repos/test-owner/test-repo/branches/main/protection", status_code=200, json={})

        # 5. Create issue
        m.post("https://api.github.com/repos/test-owner/test-repo/issues", status_code=201, json={})

        response = signed_request("/hooktest", payload, "test-secret")
        assert response.status_code == 200
        assert response.get_json() == {"message": "Success"}

        assert m.called
        # Check if restrict_commits was called with "main"
        assert m.request_history[5].url == "https://api.github.com/repos/test-owner/test-repo/branches/main/protection"
        assert m.request_history[5].method == "PUT"

        # Check if create_issue was called with the commit_url
        issue_body = m.request_history[6].json()["body"]
        assert "http://github.com/commit-url" in issue_body

def test_hooktest_success_no_initial_commit(client, signed_request, mocker):
    payload = {
        "action": "created",
        "repository": {
            "full_name": "test-owner/test-repo",
            "default_branch": "main"
        }
    }
    
    with rm.Mocker() as m:
        # 1. Check commits -> return 200 (not empty repo)
        m.get("https://api.github.com/repos/test-owner/test-repo/commits", status_code=200, json=[])

        # 2. Create CODEOWNERS
        m.put("https://api.github.com/repos/test-owner/test-repo/contents/.github/CODEOWNERS",
              status_code=201, json={})

        # 3. Restrict commits
        m.put("https://api.github.com/repos/test-owner/test-repo/branches/main/protection", status_code=200, json={})

        # 4. Create issue
        m.post("https://api.github.com/repos/test-owner/test-repo/issues", status_code=201, json={})

        response = signed_request("/hooktest", payload, "test-secret")
        assert response.status_code == 200
        assert response.get_json() == {"message": "Success"}

        # Ensure create_initial_commit (PUT /contents/README.md) was NOT called
        for req in m.request_history:
            assert "/contents/README.md" not in req.url

        # Check if create_issue was called without commit_url
        issue_body = m.request_history[3].json()["body"]
        assert "The following commit has been automatically created" not in issue_body
