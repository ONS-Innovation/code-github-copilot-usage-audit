import boto3
from botocore.exceptions import ClientError
import json
import os

import github_api_toolkit

# GitHub Organisation
org = os.getenv("GITHUB_ORG")

# GitHub App Client ID
client_id = os.getenv("GITHUB_APP_CLIENT_ID")

# AWS Secret Manager Secret Name for the .pem file
secret_name = os.getenv("AWS_SECRET_NAME")
secret_reigon = os.getenv("AWS_DEFAULT_REGION")

account = os.getenv("AWS_ACCOUNT_NAME")

# AWS Bucket Path
bucket_name = f"{account}-copilot-usage-dashboard"
object_name = "historic_usage_data.json"
file_name = "/tmp/historic_usage_data.json"


def handler(event, context):
    file_exists = True

    # Create an S3 client
    session = boto3.Session()
    s3 = session.client('s3')

    print("Session created")

    # Get historic_usage_data.json from S3
    try:
        s3.download_file(bucket_name, object_name, file_name)
    except ClientError as e:
        print(f"Error getting historic_usage_data.json from S3: {e}")
        file_exists = False
    else:
        print("Downloaded historic_usage_data.json from S3")

    # Get the .pem file from AWS Secrets Manager
    secret_manager = session.client("secretsmanager", region_name=secret_reigon)

    print("Secret Manager client created")

    secret = secret_manager.get_secret_value(SecretId=secret_name)["SecretString"]

    print("Secret retrieved")

    # Get updated copilot usage data from GitHub API
    access_token = github_api_toolkit.get_token_as_installation(org, secret, client_id)

    if type(access_token) == str:
        return(f"Error getting access token: {access_token}")
    else:
        print("Access token retrieved")

    # Create an instance of the api_controller class
    gh = github_api_toolkit.github_interface(access_token[0])

    print("API Controller created")

    # Get the usage data
    usage_data = gh.get(f"/orgs/{org}/copilot/usage")
    usage_data = usage_data.json()

    print("Usage data retrieved")

    # If historic_usage_data.json exists, load it, else create an empty list
    if file_exists:
        with open(file_name, "r") as f:
            historic_usage = json.load(f)
            print("Loaded historic_usage_data.json")
    else:
        print("No historic_usage_data.json found, creating empty list")
        historic_usage = []

    dates_added = []

    # Append the new usage data to the historic_usage_data.json
    for day in usage_data:
        if not any(d["day"] == day["day"] for d in historic_usage):
            historic_usage.append(day)

            dates_added.append(day["day"])
    
    print(f"Added {len(dates_added)} new days to historic_usage_data.json: {dates_added}")

    # Write the updated historic_usage to historic_usage_data.json
    with open(file_name, "w") as f:
        f.write(json.dumps(historic_usage, indent=4))
        print("Updated historic_usage_data.json")

    # Upload the updated historic_usage_data.json to S3
    s3.upload_file(file_name, bucket_name, object_name)

    print("Uploaded updated historic_usage_data.json to S3")

    return("Process complete")