#!/usr/bin/env sh

# Sleep 20s to make sure localstack is up and running
sleep 20

BUCKETS=(detective-test-reports)
for BUCKET in "${BUCKETS[@]}"
do
  echo "Creating ${BUCKET}..."
  /usr/local/bin/aws --endpoint-url=http://green-detective-localstack-s3:4566 s3api create-bucket --bucket ${BUCKET} --region eu-west-2 --create-bucket-configuration LocationConstraint=eu-west-2
done
