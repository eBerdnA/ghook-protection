# run debug

    export FLASK_APP=project
    export FLASK_DEBUG=1
    export GITHUB_TOKEN=OAUTH_TOKEN
    export GITHUB_OWNER=GitHub_Owner_Name
    export GITHUB_SIGNATURE=Webhook_Signature
    export APP_URL=http://localhost:5000
    flask run

# freeze requirements

    pip freeze | grep -v "pkg-resources" > requirements.txt
