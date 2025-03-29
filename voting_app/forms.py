import logging
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from .models import Poll, Choice, Vote

logger = logging.getLogger('aws_utils')

class PollForm(forms.ModelForm):
    poll_image = forms.ImageField(
        required=False, 
        help_text="Optional image for your poll (jpg, png, gif)",
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'gif'], 
                message='Only jpg, jpeg, png, and gif files are allowed.'
            )
        ]
    )
    
    class Meta:
        model = Poll
        fields = ['title', 'description', 'end_date', 'poll_image']
        widgets = {
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }
    
    def clean_poll_image(self):
        """
        Additional validation for uploaded image
        """
        image = self.cleaned_data.get('poll_image')
        
        if image:
            try:
                # Log detailed image information
                logger.info(f"Image Validation - Name: {image.name}")
                logger.info(f"Image Validation - Size: {image.size} bytes")
                logger.info(f"Image Validation - Content Type: {image.content_type}")
                
                # Check file size (e.g., limit to 5MB)
                if image.size > 5 * 1024 * 1024:  # 5MB
                    raise ValidationError("Image file too large. Maximum size is 5MB.")
                
                return image
            
            except Exception as e:
                logger.error(f"Image validation error: {e}")
                raise ValidationError(f"Invalid image: {str(e)}")
        
        return image
    
    def save(self, commit=True):
        """
        Enhanced save method with comprehensive logging and error handling
        """
        try:
            # Log all form data for debugging
            logger.info("PollForm save method called")
            logger.info(f"Form cleaned data: {self.cleaned_data}")
            
            # Create poll object
            poll = super().save(commit=False)
            
            # Handle image upload
            image = self.cleaned_data.get('poll_image')
            
            if image:
                logger.info(f"Image found: {image.name}")
                
                # Ensure poll is saved first if needed
                if not poll.pk:
                    poll.save()
                
                # Attempt to save poll image
                try:
                    result = poll.save_poll_image(image)
                    logger.info(f"Image upload result: {result}")
                    
                    if not result:
                        logger.warning("Image upload failed")
                        # Optionally add a form error
                        self.add_error('poll_image', 'Failed to upload image')
                
                except Exception as upload_error:
                    logger.error(f"Image upload error: {upload_error}")
                    self.add_error('poll_image', f'Upload failed: {str(upload_error)}')
            
            # Save poll with or without image
            if commit:
                poll.save()
            
            return poll
        
        except Exception as general_error:
            logger.error(f"Unexpected error in PollForm save: {general_error}")
            raise

class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text']

ChoiceFormSet = forms.inlineformset_factory(
    Poll, Choice, form=ChoiceForm, extra=3, min_num=2, validate_min=True
)

class VoteForm(forms.ModelForm):
    choice = forms.ModelChoiceField(queryset=None, widget=forms.RadioSelect, empty_label=None)
    
    class Meta:
        model = Vote
        fields = ['voter_name', 'voter_email', 'choice']
    
    def __init__(self, poll=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if poll:
            self.fields['choice'].queryset = Choice.objects.filter(poll=poll)