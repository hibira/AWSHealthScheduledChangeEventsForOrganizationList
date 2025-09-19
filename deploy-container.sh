#!/bin/bash

# Lambda関数名を設定
FUNCTION_NAME="eol-health-monitor"
REGION=""
ACCOUNT_ID=""
SNS_TOPIC_ANAME=""

SNS_TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:${SNS_TOPIC_ANAME}"
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${FUNCTION_NAME}"

# IAMロールを作成（存在しない場合）
aws iam get-role --role-name lambda-execution-role 2>/dev/null || \
(aws iam create-role --role-name lambda-execution-role --assume-role-policy-document file://trust-policy.json && \
aws iam put-role-policy --role-name lambda-execution-role --policy-name eol-health-policy --policy-document file://iam-policy.json)

# IAMポリシーを更新（既存の場合）
aws iam put-role-policy --role-name lambda-execution-role --policy-name eol-health-policy --policy-document file://iam-policy.json

# ECRリポジトリを作成（存在しない場合）
aws ecr describe-repositories --repository-names ${FUNCTION_NAME} --region ${REGION} || \
aws ecr create-repository --repository-name ${FUNCTION_NAME} --region ${REGION}

# ECRにログイン
aws ecr get-login-password --region ${REGION} | finch login --username AWS --password-stdin ${ECR_REPO}

# Finchでイメージをビルド（x86_64アーキテクチャを指定）
finch build --platform linux/amd64 -t ${FUNCTION_NAME} .

# イメージにタグを付けてプッシュ
finch tag ${FUNCTION_NAME}:latest ${ECR_REPO}:latest
finch push ${ECR_REPO}:latest

# Lambda関数を作成または更新
if aws lambda get-function --function-name ${FUNCTION_NAME} --region ${REGION} >/dev/null 2>&1; then
  # 既存の関数を更新
  aws lambda update-function-code --function-name ${FUNCTION_NAME} --image-uri ${ECR_REPO}:latest --region ${REGION}
  aws lambda update-function-configuration \
    --function-name ${FUNCTION_NAME} \
    --environment Variables={SNS_TOPIC_ARN="${SNS_TOPIC_ARN}"} \
    --region ${REGION}
else
  # 新しい関数を作成
  sleep 10
  aws lambda create-function \
    --function-name ${FUNCTION_NAME} \
    --package-type Image \
    --code ImageUri=${ECR_REPO}:latest \
    --role arn:aws:iam::${ACCOUNT_ID}:role/lambda-execution-role \
    --timeout 900 \
    --memory-size 512 \
    --environment Variables={SNS_TOPIC_ARN="${SNS_TOPIC_ARN}"} \
    --region ${REGION}
fi

echo "デプロイ完了: ${FUNCTION_NAME}"