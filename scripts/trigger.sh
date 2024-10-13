#!/bin/bash
usage() {
    echo "Usage: $0 -p <project> -r <region> -t <trigger> [-b <branch>] [-s <substitutions>] [-i <impersonate-service-account>]"
    exit 1
}

while getopts "p:r:t:b:s:i:" opt; do
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

if [ -z "$project" ] || [ -z "$region" ] || [ -z "$trigger" ]; then
    usage
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS=1

gcloud config set project "$project"

IMPERSONATE_FLAG=""
if [ -n "$impersonate" ]; then
    IMPERSONATE_FLAG="--impersonate-service-account=$impersonate"
fi

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

echo "starting build $BUILD_ID..."
echo "Build log is available in GCP console. Go there for debugging details"

while true; do
    BUILD_STATUS=$(gcloud beta builds describe "$BUILD_ID" --format="value(status)" --region="$region")
    if [ "$BUILD_STATUS" == "SUCCESS" ]; then
        echo "Build status = $BUILD_STATUS. Go to GCP Console for logs."
        exit 0
    elif [ "$BUILD_STATUS" == "FAILURE" ] || [ "$BUILD_STATUS" == "CANCELLED" ]; then
        echo "Build status = $BUILD_STATUS. Go to GCP Console for logs."
        exit 1
    fi
    sleep 60
done
