#!/usr/bin/env python3

# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Deploy frontend files directly to S3 and invalidate CloudFront
This script uploads the frontend files and creates the necessary configuration
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def deploy_frontend(stack_name: str, region: str, profile: str = None):
    """Deploy frontend files to S3 and invalidate CloudFront"""

    # Create session with profile if specified
    if profile:
        session = boto3.Session(profile_name=profile)
        logger.info(f"Using AWS profile: {profile}")
    else:
        session = boto3.Session()
        logger.info("Using default AWS credentials")

    cf_client = session.client("cloudformation", region_name=region)
    s3_client = session.client("s3", region_name=region)
    cloudfront_client = session.client("cloudfront", region_name=region)

    try:
        # Get stack outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        stack = response["Stacks"][0]

        outputs = {}
        if "Outputs" in stack:
            for output in stack["Outputs"]:
                outputs[output["OutputKey"]] = output["OutputValue"]

        # Get required values
        frontend_bucket = outputs.get("FrontendBucketName")
        cloudfront_domain = outputs.get("CloudFrontDomainName")
        user_pool_id = outputs.get("UserPoolId")
        web_app_client_id = outputs.get("WebAppClientId")
        api_client_id = outputs.get("APIClientId")
        # mcp_server_client_id = outputs.get("MCPServerClientId")
        user_pool_domain = outputs.get("UserPoolDomain")

        if not all(
            [frontend_bucket, cloudfront_domain, user_pool_id, web_app_client_id]
        ):
            logger.error("Missing required stack outputs")
            return False

        logger.info(f"Deploying to bucket: {frontend_bucket}")
        logger.info(f"CloudFront domain: {cloudfront_domain}")

        # Create frontend configuration
        config_js = f"""window.APP_CONFIG = {{
    "cognito": {{
        "userPoolId": "{user_pool_id}",
        "clientId": "{web_app_client_id}",
        "domain": "{user_pool_domain}"
    }},
    "api": {{
        "baseUrl": "https://{cloudfront_domain}",
        "endpoints": {{
            "chat": "https://{cloudfront_domain}/api/chat",
            "health": "https://{cloudfront_domain}/api/health",
            "websocket": "wss://{cloudfront_domain}/ws"
        }}
    }},
    "app": {{
        "name": "Cloud Optimization Platform",
        "version": "1.0.0"
    }}
}};"""

        # Upload configuration file
        s3_client.put_object(
            Bucket=frontend_bucket,
            Key="config.js",
            Body=config_js,
            ContentType="application/javascript",
        )
        logger.info("✅ Uploaded config.js")

        # Upload frontend files
        frontend_dir = (
            Path(__file__).parent.parent
            / "cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend"
        )

        if not frontend_dir.exists():
            logger.error(f"Frontend directory not found: {frontend_dir}")
            return False

        # Upload HTML files
        for html_file in frontend_dir.glob("*.html"):
            with open(html_file, "r") as f:
                content = f.read()

            s3_client.put_object(
                Bucket=frontend_bucket,
                Key=html_file.name,
                Body=content,
                ContentType="text/html",
            )
            logger.info(f"✅ Uploaded {html_file.name}")

        # Upload CSS files if any
        for css_file in frontend_dir.glob("*.css"):
            with open(css_file, "r") as f:
                content = f.read()

            s3_client.put_object(
                Bucket=frontend_bucket,
                Key=css_file.name,
                Body=content,
                ContentType="text/css",
            )
            logger.info(f"✅ Uploaded {css_file.name}")

        # Upload JS files if any (excluding config.js template)
        for js_file in frontend_dir.glob("*.js"):
            if js_file.name.endswith(".template"):
                continue

            with open(js_file, "r") as f:
                content = f.read()

            s3_client.put_object(
                Bucket=frontend_bucket,
                Key=js_file.name,
                Body=content,
                ContentType="application/javascript",
            )
            logger.info(f"✅ Uploaded {js_file.name}")

        # Get CloudFront distribution ID
        distributions = cloudfront_client.list_distributions()
        distribution_id = None

        for dist in distributions["DistributionList"]["Items"]:
            if dist["DomainName"] == cloudfront_domain:
                distribution_id = dist["Id"]
                break

        if distribution_id:
            # Create CloudFront invalidation
            response = cloudfront_client.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    "Paths": {"Quantity": 1, "Items": ["/*"]},
                    "CallerReference": f"frontend-deploy-{int(time.time())}",
                },
            )
            logger.info(
                f"✅ Created CloudFront invalidation: {response['Invalidation']['Id']}"
            )
        else:
            logger.warning("Could not find CloudFront distribution ID for invalidation")

        logger.info("🎉 Frontend deployment completed successfully!")
        logger.info(f"🌐 Access your application at: https://{cloudfront_domain}")

        return True

    except ClientError as e:
        logger.error(f"AWS error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Deploy frontend files to S3 and invalidate CloudFront"
    )
    parser.add_argument(
        "--stack-name",
        default="cloud-optimization-assistant",
        help="CloudFormation stack name",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--profile", help="AWS CLI profile name")

    args = parser.parse_args()

    success = deploy_frontend(args.stack_name, args.region, args.profile)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
