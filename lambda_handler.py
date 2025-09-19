#!/usr/bin/env python3
import json
import os
import boto3
from datetime import datetime
from get_eol_health import get_eol_health_events, analyze_with_bedrock

def format_analysis_for_slack(analysis):
    """分析結果をSlack表示用に縦並びフォーマットに変換"""
    lines = analysis.strip().split('\n')
    formatted_lines = []
    headers = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 表形式の区切り線をスキップ
        if line.startswith('|--') or line.startswith('---'):
            continue
        
        if '|' in line:
            parts = [part.strip() for part in line.split('|') if part.strip()]
            if not headers and len(parts) > 1:
                # ヘッダー行を保存
                headers = parts
            elif headers and len(parts) > 1:
                # データ行を縦並びに変換
                formatted_lines.append(f"\n *{parts[0]}* :")
                for i, value in enumerate(parts[1:], 1):
                    if i < len(headers):
                        formatted_lines.append(f"  • {headers[i]}: {value}")
        else:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

def send_sns_notification(analysis, event_count):
    """AWS ChatBot用のSNS通知を送信"""
    sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
    if not sns_topic_arn:
        print("SNS_TOPIC_ARN環境変数が設定されていません")
        return False
    
    try:
        sns_client = boto3.client('sns', region_name='us-east-1')
        
        # Amazon Q Developer custom notifications形式
        chatbot_message = {
            "version": "1.0",
            "source": "custom",
            "content": {
                "textType": "client-markdown",
                "title": f":warning: AWS Health EOL Events Alert - {event_count}件のイベント検出",
                "description": f"EOL関連のイベントが検出されました。\n\n## 分析結果\n\n{format_analysis_for_slack(analysis)}\n\n## 詳細確認\n\n[AWS Health Dashboard](https://health.aws.amazon.com/health/home)",
                "nextSteps": [
                    "Refer to <https://health.aws.amazon.com/health/home|AWS Health Dashboard>"
                ],
            }
        }
        
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=json.dumps(chatbot_message, ensure_ascii=False)
        )
        print(f"ChatBot通知送信完了: {sns_topic_arn}")
        return True
    except Exception as e:
        print(f"SNS通知送信エラー: {e}")
        return False

def lambda_handler(event, context):
    """AWS Lambda用のハンドラー関数"""
    
    try:
        print("AWS Organizations Health - 組織全体のEOL関連イベント取得開始")
        
        # EOLイベントを取得
        eol_events = get_eol_health_events()
        
        if not eol_events:
            print("EOL関連のイベントは見つかりませんでした。SNS通知はスキップします。")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'EOL関連のイベントは見つかりませんでした。',
                    'eventCount': 0
                }, ensure_ascii=False)
            }
        
        print(f"{len(eol_events)}件のイベントが見つかりました。")
        
        # Bedrockで分析
        analysis = analyze_with_bedrock(eol_events)
        
        if analysis:
            # ChatBot通知を送信
            send_sns_notification(analysis, len(eol_events))
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'{len(eol_events)}件のEOLイベントを分析し、SNS通知を送信しました。',
                    'eventCount': len(eol_events),
                    'analysis': analysis
                }, ensure_ascii=False)
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Bedrock分析に失敗しました。',
                    'eventCount': len(eol_events),
                    'events': eol_events
                }, ensure_ascii=False)
            }
            
    except Exception as e:
        print(f"Lambda実行エラー: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            }, ensure_ascii=False)
        }