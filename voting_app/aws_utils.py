import boto3
import json
import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# Configure logging
logger = logging.getLogger('aws_utils')

def get_aws_clients():
    """
    Create and return AWS clients with robust error handling
    """
    # Validate AWS credentials
    required_keys = [
        'AWS_ACCESS_KEY_ID', 
        'AWS_SECRET_ACCESS_KEY', 
        'AWS_REGION', 
        'AWS_SNS_TOPIC_ARN', 
        'AWS_LAMBDA_FUNCTION_ARN'
    ]
    
    # Log all credentials for debugging (be careful in production)
    logger.info("Attempting to create AWS clients")
    for key in required_keys:
        value = getattr(settings, key, 'NOT SET')
        logger.info(f"{key}: {value}")
    
    try:
        # Create AWS session with explicit credentials
        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            aws_session_token=settings.AWS_SESSION_TOKEN,  # Add session token
            region_name=settings.AWS_REGION
        )
        
        # Create AWS clients using session
        sns_client = session.client('sns')
        lambda_client = session.client('lambda')
        
        return sns_client, lambda_client
    except Exception as e:
        logger.error(f"DETAILED AWS CLIENT CREATION ERROR: {str(e)}", exc_info=True)
        raise

def send_poll_notification(poll):
    """
    Send a notification about a new poll using AWS SNS
    """
    try:
        # Get AWS clients
        sns_client, _ = get_aws_clients()
        
        # Prepare message
        message = {
            'poll_id': poll.id,
            'poll_title': poll.title,
            'poll_description': poll.description,
            'poll_end_date': poll.end_date.isoformat(),
            'created_at': poll.created_at.isoformat()
        }
        
        # Publish to SNS topic
        response = sns_client.publish(
            TopicArn=settings.AWS_SNS_TOPIC_ARN,
            Message=json.dumps(message),
            Subject='New Poll Created'
        )
        
        # Log successful notification
        logger.info(f"SNS notification sent for poll: {poll.title}")
        return response
    except Exception as e:
        # Log the error with more detailed information
        logger.error(f"DETAILED SNS NOTIFICATION ERROR: {str(e)}", exc_info=True)
        raise  # Re-raise to allow higher-level error handling

def invoke_poll_notification_lambda(poll):
    """
    Invoke Lambda function to process poll notification
    """
    try:
        # Get AWS clients
        _, lambda_client = get_aws_clients()
        
        # Prepare payload
        payload = {
            'poll_id': poll.id,
            'poll_title': poll.title,
            'poll_description': poll.description,
            'poll_end_date': poll.end_date.isoformat(),
            'created_at': poll.created_at.isoformat()
        }
        
        # Invoke Lambda function
        response = lambda_client.invoke(
            FunctionName=settings.AWS_LAMBDA_FUNCTION_ARN,
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps(payload)
        )
        
        # Log successful Lambda invocation
        logger.info(f"Lambda function invoked for poll: {poll.title}")
        return response
    except Exception as e:
        # Log the error with more detailed information
        logger.error(f"DETAILED LAMBDA INVOCATION ERROR: {str(e)}", exc_info=True)
        raise  # Re-raise to allow higher-level error handling