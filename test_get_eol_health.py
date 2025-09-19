#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
import json
from get_eol_health import get_affected_accounts, get_affected_entities, get_event_details, analyze_with_bedrock

class TestEOLHealthMonitor(unittest.TestCase):

    @patch('get_eol_health.boto3.client')
    def test_get_affected_accounts_success(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        mock_client.describe_affected_accounts_for_organization.return_value = {
            'affectedAccounts': ['123456789012', '987654321098']
        }
        
        result = get_affected_accounts('arn:aws:health:us-east-1::event/test')
        self.assertEqual(result, ['123456789012', '987654321098'])

    @patch('get_eol_health.boto3.client')
    def test_get_affected_accounts_exception(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        mock_client.describe_affected_accounts_for_organization.side_effect = Exception("API Error")
        
        result = get_affected_accounts('arn:aws:health:us-east-1::event/test')
        self.assertEqual(result, [])

    @patch('get_eol_health.boto3.client')
    def test_get_affected_entities_success(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        mock_client.describe_affected_entities_for_organization.return_value = {
            'entities': [{
                'entityArn': 'arn:aws:lambda:us-east-1:123456789012:function:test',
                'entityValue': 'test-function',
                'awsAccountId': '123456789012',
                'tags': {}
            }]
        }
        
        result = get_affected_entities('arn:aws:health:us-east-1::event/test')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['entityValue'], 'test-function')

    @patch('get_eol_health.boto3.client')
    def test_get_event_details_success(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        mock_client.describe_event_details_for_organization.return_value = {
            'successfulSet': [{
                'eventDescription': {
                    'latestDescription': 'Python 3.9 runtime will be deprecated'
                },
                'eventMetadata': {'platform': 'python3.9'}
            }]
        }
        
        result = get_event_details('arn:aws:health:us-east-1::event/test', ['123456789012'])
        self.assertEqual(result['description'], 'Python 3.9 runtime will be deprecated')

    @patch('get_eol_health.boto3.client')
    def test_analyze_with_bedrock_success(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.return_value = mock_client
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'content': [{'text': '| Account | Service | Platform | Version |\n|---------|---------|----------|---------|'}]
        }).encode()
        mock_client.invoke_model.return_value = {'body': mock_response}
        
        test_data = [{'service': 'LAMBDA', 'description': 'Python 3.9 deprecation'}]
        result = analyze_with_bedrock(test_data)
        self.assertIn('Account', result)
        self.assertIn('Service', result)

if __name__ == '__main__':
    unittest.main()