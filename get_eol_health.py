#!/usr/bin/env python3
import boto3
import json

def get_affected_accounts(event_arn):
    """特定のイベントで影響を受けるアカウントを取得"""
    health_client = boto3.client('health', region_name='us-east-1')
    
    try:
        response = health_client.describe_affected_accounts_for_organization(
            eventArn=event_arn
        )
        return response.get('affectedAccounts', [])
    except Exception as e:
        return []

def get_affected_entities(event_arn):
    """影響を受けるリソースの詳細を取得"""
    health_client = boto3.client('health', region_name='us-east-1')
    
    try:
        response = health_client.describe_affected_entities_for_organization(
            organizationEntityFilters=[
                {
                    'eventArn': event_arn
                }
            ]
        )
        
        entities = []
        for entity in response.get('entities', []):
            entities.append({
                'entityArn': entity.get('entityArn', ''),
                'entityValue': entity.get('entityValue', ''),
                'awsAccountId': entity.get('awsAccountId', ''),
                'tags': entity.get('tags', {})
            })
        
        return entities
    except Exception as e:
        return []

def get_event_details(event_arn, affected_accounts):
    """イベントの詳細情報を取得"""
    health_client = boto3.client('health', region_name='us-east-1')
    
    if not affected_accounts:
        return {'description': '', 'eventMetadata': {}}
    
    try:
        # 最初のアカウントIDを使用して詳細情報を取得
        response = health_client.describe_event_details_for_organization(
            organizationEventDetailFilters=[
                {
                    'eventArn': event_arn,
                    'awsAccountId': affected_accounts[0]
                }
            ]
        )

        if response.get('successfulSet'):
            event_detail = response['successfulSet'][0]
            return {
                'description': event_detail.get('eventDescription', {}).get('latestDescription', ''),
                'eventMetadata': event_detail.get('eventMetadata', {})
            }
        
        return {'description': '', 'eventMetadata': {}}
    except Exception as e:
        print(f"イベント詳細取得エラー: {e}")
        return {'description': '', 'eventMetadata': {}}

def get_eol_health_events():
    """AWS Organizations Health APIから組織全体のEOL関連イベントを取得"""
    
    health_client = boto3.client('health', region_name='us-east-1')
    
    try:
        all_events = []
        next_token = None
        
        while True:
            params = {
                'filter': {
                    'eventTypeCategories': ['scheduledChange'],
                    'eventStatusCodes': ['upcoming', 'open']
                },
                'maxResults': 100
            }
            
            if next_token:
                params['nextToken'] = next_token
            
            response = health_client.describe_events_for_organization(**params)
            all_events.extend(response['events'])
            
            next_token = response.get('nextToken')
            if not next_token:
                break
        
        print(f"全件取得されたイベント数: {len(all_events)}")
        
        eol_events = []
        
        for event in all_events:         
            print(f"イベント: {event['service']} - {event['eventTypeCode']} - {event['region']} - {event['statusCode']}")

            # 影響を受けるアカウントを取得
            affected_accounts = get_affected_accounts(event['arn'])
            
            # イベントの詳細情報を取得
            event_details = get_event_details(event['arn'], affected_accounts)
            
            # 影響を受けるリソースの詳細を取得
            affected_entities = get_affected_entities(event['arn'])
            
            eol_events.append({
                'arn': event['arn'],
                'service': event['service'],
                'eventTypeCode': event['eventTypeCode'],
                'region': event['region'],
                'startTime': str(event.get('startTime', '')),
                'endTime': str(event.get('endTime', '')),
                'statusCode': event['statusCode'],
                'affectedAccounts': affected_accounts,
                'description': event_details['description'],
                'eventMetadata': event_details['eventMetadata'],
                'affectedEntities': affected_entities
            })
        
        return eol_events
        
    except Exception as e:
        print(f"エラー: {e}")
        return []

def extract_version_from_description(description, metadata):
    """通知内容からバージョン情報を抽出"""
    description_lower = description.lower()
    
    if 'python 3.9' in description_lower:
        return 'Python', 'Python 3.9'
    elif 'python 3.8' in description_lower:
        return 'Python', 'Python 3.8'
    elif 'node.js 18' in description_lower:
        return 'Node.js', 'Node.js 18'
    elif 'nodejs18' in description_lower:
        return 'Node.js', 'Node.js 18'
    
    # metadataからも推測
    metadata_str = str(metadata).lower()
    if 'python 3.9' in metadata_str:
        return 'Python', 'Python 3.9'
    elif 'python 3.8' in metadata_str:
        return 'Python', 'Python 3.8'
    elif 'node.js 18' in metadata_str:
        return 'Node.js', 'Node.js 18'
    
    return 'Unknown', 'Unknown'

def analyze_with_bedrock(events_data):
    """Bedrock Claude 3.7を使ってEOLイベントを分析し表形式で出力"""
    
    bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    # 通知内容からバージョン情報を抽出してデータを強化
    enhanced_events = []
    for event in events_data:
        platform, version = extract_version_from_description(event.get('description', ''), event.get('eventMetadata', {}))
        enhanced_event = event.copy()
        enhanced_event['inferred_platform'] = platform
        enhanced_event['inferred_version'] = version
        enhanced_events.append(enhanced_event)
    
    prompt = f"""以下のAWS Health EOLイベントデータを分析し、指定された形式の表でまとめてください。

データ:
{json.dumps(enhanced_events, indent=2, ensure_ascii=False)}

必須カラム形式:
| アカウントID | サービス名 | プラットフォーム | バージョン | サポート終了日 | 関連リージョン | ステータス | サマリー |

要件:
1. アカウントIDは実際の値を表示（複数の場合は「161957781465 他3つ」形式）
2. プラットフォームとバージョンはinferred_platform、inferred_versionを使用
4. 関連リージョンは複数の場合カンマ区切り
5. サポート終了日はYYYY/MM/DD形式
6. 同じアカウント・サービス・バージョンは1行にまとめる
7. サマリーには通知内容から重要なポイントを1行で簡潔に記載

表のみ出力し、余計な説明は不要です。"""

    try:
        response = bedrock_client.invoke_model(
            modelId='us.anthropic.claude-3-7-sonnet-20250219-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 80000,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        return result['content'][0]['text']
        
    except Exception as e:
        print(f"Bedrock分析エラー: {e}")
        return None

def main():
    """メイン処理"""
    print("AWS Organizations Health - 組織全体のEOL関連イベント取得中...")
    
    eol_events = get_eol_health_events()
    
    if not eol_events:
        print("EOL関連のイベントは見つかりませんでした。")
        return
    
    print(f"{len(eol_events)}件のイベントが見つかりました。")
    
    # 抽出されたバージョン情報を表示
    print("\n=== 抽出されたバージョン情報 ===")
    for event in eol_events:
        platform, version = extract_version_from_description(event.get('description', ''), event.get('eventMetadata', {}))
        print(f"サービス: {event['service']}, 開始日: {event['startTime'][:10]}, 抽出: {platform} {version}")
    
    print("\nBedrock Claude 3.7で分析中...")
    
    analysis = analyze_with_bedrock(eol_events)
    
    if analysis:
        print(analysis)
    else:
        print("分析に失敗しました。生データを表示します:")
        for event in eol_events:
            print(f"サービス: {event['service']}, リージョン: {event['region']}, "
                  f"イベント: {event['eventTypeCode']}, アカウント数: {len(event['affectedAccounts'])}")

if __name__ == "__main__":
    main()
