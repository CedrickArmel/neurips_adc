#!/bin/bash
usage() {
    echo "Usage: $0 -p <project> -r <region> -t <trigger> [-b <branch>] [-s <substitutions>] [-i <impersonate-service-account>]"
    exit 1
}

while getopts "p:r:t:b:s:" opt; do
    case $opt in
        p) project="$OPTARG";;
        r) region="$OPTARG";;
        t) trigger="$OPTARG";;
        b) branch="$OPTARG";;
        s) substitutions="$OPTARG";;
        i) impersonate="$OPTARG";;
        *) usage;;
    esac
done

# Check if mandatory parameters are provided
if [ -z "$project" ] || [ -z "$region" ] || [ -z "$trigger" ]; then
    usage
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS=1

# Set the project
gcloud config set project "$project"

IMPERSONATE_FLAG=""
if [ -n "$impersonate" ]; then
    IMPERSONATE_FLAG="--impersonate-service-account=$impersonate"
fi

# Run the gcloud command based on whether the branch and substitutions are provided
if [ -z "$substitutions" ]; then
    if [ -z "$branch" ]; then
        BUILD_ID=$(gcloud beta builds triggers run "$trigger" --region="$region" $IMPERSONATE_FLAG --quiet --format="value(metadata.build.id)")
    else
        BUILD_ID=$(gcloud beta builds triggers run "$trigger" --region="$region" --branch="$branch" $IMPERSONATE_FLAG --quiet --format="value(metadata.build.id)")
    fi
else
    if [ -z "$branch" ]; then
        BUILD_ID=$(gcloud beta builds triggers run "$trigger" --region="$region" --substitutions="$substitutions" $IMPERSONATE_FLAG --quiet --format="value(metadata.build.id)")
    else
        BUILD_ID=$(gcloud beta builds triggers run "$trigger" --region="$region" --substitutions="$substitutions" $IMPERSONATE_FLAG --branch="$branch" --quiet --format="value(metadata.build.id)")
    fi
fi

# Output the BUILD_ID
echo "BUILD_ID = $BUILD_ID"

# Stream the logs
gcloud beta builds log --stream "$BUILD_ID" --region="$region"

# Get the build status
BUILD_STATUS=$(gcloud beta builds describe "$BUILD_ID" --format="value(status)" --region="$region")
echo "Build status = $BUILD_STATUS"

# Exit based on build status
if [ "$BUILD_STATUS" == "SUCCESS" ]; then
    exit 0
else
    exit 1
fi
