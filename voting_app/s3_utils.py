import boto3
import uuid
from django.conf import settings
import logging
import traceback
import mimetypes
import io

logger = logging.getLogger('aws_utils')

def get_aws_session():
    """
    Create and return an AWS session with explicit credentials
    """
    try:
        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            aws_session_token=settings.AWS_SESSION_TOKEN,
            region_name=settings.AWS_REGION
        )
        return session
    except Exception as e:
        logger.error(f"Error creating AWS session: {str(e)}")
        raise

def upload_file_to_s3(file, folder='polls/'):
    """
    Upload a file to S3 bucket with comprehensive error handling and logging.
    """
    try:
        if not file:
            logger.error("No file provided for upload")
            return None

        # Enhanced file logging
        logger.info(f"Preparing to upload file")
        logger.info(f"File name: {file.name}")
        logger.info(f"File size: {file.size} bytes")
        logger.info(f"Reported content type: {getattr(file, 'content_type', 'Unknown')}")

        # Try to guess content type if not provided
        content_type = getattr(file, 'content_type', None) or mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        logger.info(f"Determined content type: {content_type}")

        # Generate unique filename
        unique_filename = generate_unique_filename(file.name)
        full_path = f"{folder}{unique_filename}"
        logger.info(f"Generated unique filename: {full_path}")

        # Create S3 client
        session = get_aws_session()
        s3_client = session.client('s3')

        # Create an in-memory file-like object
        file_buffer = io.BytesIO(file.read())
        file_buffer.seek(0)

        # Perform upload
        try:
            s3_client.upload_fileobj(
                file_buffer, 
                settings.AWS_STORAGE_BUCKET_NAME, 
                full_path,
                ExtraArgs={
                    'ContentType': content_type,
                    'ACL': 'public-read'
                }
            )
        except Exception as upload_error:
            logger.error(f"S3 Upload Failure: {upload_error}")
            logger.error(traceback.format_exc())
            return None
        
        # Construct and return S3 URL
        s3_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{full_path}"
        logger.info(f"File successfully uploaded to: {s3_url}")
        return s3_url
    except Exception as e:
        logger.error(f"Comprehensive S3 Upload Error: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def generate_unique_filename(original_filename):
    """
    Generate a unique filename to prevent conflicts in S3
    """
    ext = original_filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{ext}"
    return unique_filename

def delete_file_from_s3(file_url):
    """
    Delete a file from S3 bucket
    
    Args:
        file_url: S3 URL of the file to delete
    
    Returns:
        Boolean indicating success or failure
    """
    try:
        # If file_url is an S3 URL, proceed with deletion
        if isinstance(file_url, str) and file_url.startswith('https://'):
            # Create S3 client
            session = get_aws_session()
            s3_client = session.client('s3')
            
            # Extract object key from S3 URL
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            object_key = file_url.split(f"{bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/")[1]
            
            # Delete file from S3
            s3_client.delete_object(
                Bucket=bucket_name,
                Key=object_key
            )
            logger.info(f"File deleted successfully from S3: {file_url}")
            return True
        else:
            logger.warning(f"Invalid file URL for deletion: {file_url}")
            return False
    except Exception as e:
        logger.error(f"Error deleting file from S3: {str(e)}")
        return False