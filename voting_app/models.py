from django.db import models
from django.utils import timezone
import logging
from .s3_utils import upload_file_to_s3, delete_file_from_s3

logger = logging.getLogger('aws_utils')

class Poll(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    
    # Optional: Add S3 file support
    poll_image = models.CharField(max_length=500, blank=True, null=True)
    
    def __str__(self):
        return self.title
    
    def is_active(self):
        return timezone.now() <= self.end_date
    
    def save_poll_image(self, image_file):
        """
        Save poll image to S3 and update poll_image field with enhanced logging
        """
        try:
            logger.info(f"save_poll_image method called")
            logger.info(f"Image file type: {type(image_file)}")
            
            if not image_file:
                logger.warning("No image file provided")
                return False
            
            logger.info(f"Image file name: {image_file.name}")
            logger.info(f"Image file size: {image_file.size}")
            logger.info(f"Image content type: {image_file.content_type}")
            
            # Delete existing image if it exists
            if self.poll_image:
                try:
                    delete_file_from_s3(self.poll_image)
                    logger.info(f"Deleted existing image: {self.poll_image}")
                except Exception as e:
                    logger.error(f"Error deleting existing image: {e}")
            
            # Upload new image
            try:
                s3_url = upload_file_to_s3(image_file)
                
                if s3_url:
                    self.poll_image = s3_url
                    # Directly save the model to update the image URL
                    self.save(update_fields=['poll_image'])
                    logger.info(f"Image uploaded successfully. S3 URL: {s3_url}")
                    return True
                else:
                    logger.error("Failed to upload image to S3")
                    return False
            except Exception as e:
                logger.error(f"Comprehensive upload error: {e}", exc_info=True)
                return False
        
        except Exception as general_error:
            logger.error(f"Unexpected error in save_poll_image: {general_error}", exc_info=True)
            return False

# Rest of the models remain the same
class Choice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=200)
    
    def __str__(self):
        return self.text

class Vote(models.Model):
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE, related_name='votes')
    voter_name = models.CharField(max_length=100)
    voter_email = models.EmailField()
    voted_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Check if this email has already voted in this poll
        if not self.pk:  # Only on create
            poll = self.choice.poll
            if Vote.objects.filter(
                choice__poll=poll,
                voter_email=self.voter_email
            ).exists():
                from django.db import IntegrityError
                raise IntegrityError('This email has already voted in this poll.')
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.voter_name} voted for {self.choice.text}"