# AWS Health EOL Events Monitor

AWS Organizations Health APIを使用して組織全体のEOL（End of Life）関連イベントを取得し、Amazon Bedrockで分析してSlack/ChatBotに通知するLambda関数。

## 機能

- AWS Organizations Health APIから組織全体のスケジュール変更イベントを取得
- 影響を受けるアカウント・リソースの詳細情報を収集
- Amazon Bedrock Claude 3.7を使用してプラットフォーム、バージョン、サポート終了日を自動抽出
- AWS ChatBot経由でSlackに通知（Custom notifications形式）
- コンテナイメージとしてLambdaにデプロイ

## アーキテクチャ

```
Lambda Function (Container) → AWS Health API → Amazon Bedrock → SNS → AWS ChatBot → Slack
```

## 前提条件

- AWS Organizations管理アカウントでの実行
- 以下の権限を持つIAMロール：
  - `health:DescribeEventsForOrganization`
  - `health:DescribeAffectedAccountsForOrganization`
  - `health:DescribeAffectedEntitiesForOrganization`
  - `health:DescribeEventDetailsForOrganization`
  - `organizations:ListAccounts`
  - `bedrock:InvokeModel`
  - `sns:Publish`
- SNSトピックとAWS ChatBot設定
- Finch（コンテナビルド用）

## デプロイ方法

```bash
# デプロイスクリプトを実行
./deploy-container.sh
```

## 設定ファイル

- `Dockerfile`: Lambda用コンテナイメージ定義
- `requirements.txt`: Python依存関係
- `iam-policy.json`: Lambda実行ロール用IAMポリシー
- `trust-policy.json`: IAMロール信頼ポリシー

## 環境変数

- `SNS_TOPIC_ARN`: 通知先SNSトピックのARN

## 通知形式

Slackには以下の形式で通知されます：

```
⚠️ AWS Health EOL Events Alert - X件のイベント検出

EOL関連のイベントが検出されました。

## 分析結果

**1234567890 他4つ**:
  • サービス名: LAMBDA
  • プラットフォーム: Python
  • バージョン: 3.9
  • サポート終了日: 2025/12/15
  • 関連リージョン: eu-central-1 他11個
  • ステータス: upcoming
  • サマリー: Python 3.9のEOL到達により、Lambdaでのサポートが終了...

**1234567890**:
  • サービス名: LAMBDA
  • プラットフォーム: Node.js
  • バージョン: 18
  • サポート終了日: 2025/09/01
  • 関連リージョン: us-east-1, us-west-2
  • ステータス: open
  • サマリー: Node.js 18のEOL到達により、Lambdaでのサポートが終了...

## 詳細確認

AWS Health Dashboard
```

## 主な対象サービス

- AWS Lambda（Python/Node.js ランタイム）
- Amazon ECS
- CloudWatch Synthetics
- AWS WAF Classic
- Amazon Lex V1
- その他のライフサイクル変更対象サービス

## 注意事項

- us-east-1リージョンでの実行が必要
- 組織管理アカウントでの実行が必須
- 大量のイベントがある場合、Bedrock分析に時間がかかる場合があります
- Lambda実行時間は最大15分（900秒）に設定