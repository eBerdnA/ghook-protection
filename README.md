# Introduction

This project can be used to auto protect the master/main branch of newly created GitHub projects. The protection process is triggered by [GitHub Webhooks](https://docs.github.com/en/developers/webhooks-and-events/webhooks/about-webhooks). Please note that this is only possible for projects inside an [Organizations](https://docs.github.com/en/organizations). Because only organizations provide the necessary [webhook](https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#project) for acting upon project creation.

The current implementation does only act upon the action `created`. Any other actions are ignored.

# Development

## Run debug

Clone the project and perform the following steps. Replace the values in brackets (removing the brackets) with correspondig values for your environment.

    cd <project-name>
    pip install -r requirements.txt
    export FLASK_APP=project
    export FLASK_DEBUG=1
    export GITHUB_TOKEN=<OAUTH_TOKEN>
    export GITHUB_OWNER=<GitHub_Owner_Name>
    export GITHUB_SECRET=<Webhook_Secret>
    export APP_URL=<http://localhost:5000>
    flask run

During development it could be easier to run this locally and make the webhook publicly available using a service like [ngrok](https://ngrok.com/). Please consult their [documentation](https://ngrok.com/docs) on which steps are necessary to do this.

## Freeze requirements

When addtional requirements are added to the project please use the following command to update the requirements file.

    pip freeze | grep -v "pkg-resources" > requirements.txt

# Production

## Run

Build the docker image and make it available to your server.
For running the docker image the provided `docker-compose.yml` can be used as a starting point.
The `.env.sample` can be used as a starting point for the needed `.env` file.

**It is important that the variable `FLASK_ENV` is set to `production` and `FLASK_DEBUG` to `0`. In debug mode the signature validation is bypassed which is not recommend in a production environment.**

The following values must be changed for your individual needs/environment.

| environment variable | description | example |
|--|--|--|
| GITHUB_TOKEN | The [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) (OAuth) for GitHub which can be used to interact with the API. The token must be for an account which has admin permission in the orgnization because only accounts with admin permissions can manage branch protection rules [Managing a branch protection rule - GitHub Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/managing-a-branch-protection-rule). | abcdefghijklmnopqrstuvwxyz_0123456789abc |
| GITHUB_OWNER | The GitHub handle of the person which should be mentioned | eberdna |
| GITHUB_SECRET | The secret which is configured for the webhook at GitHub | Test1234 |
| APP_URL | The URL under which the webhook application publicly accessible | https://myhook.example.org |

## Configure Webhook

If the example `APP_URL` from the example would be used, you need to set the »Payload URL« of the webhook in the GitHub configuration of your Organization to the following endpoint: `https://myhook.example.org/hooktest`. In addition the »Content Type« must be set to `application/json`.

The only relevant event is »Repositories«. All other events must be unchecked during configuration.

# Known Issues

- The provided `default_branch` in the webhook payload is `master` even though the setting at organization level is set to `main`. Therefore the value for `default_branch` is hard coded to `main`. This must be changed once the payload does include the right `default_branch` information.
