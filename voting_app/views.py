from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.db import IntegrityError

import logging

logger = logging.getLogger(__name__) 

from .models import Poll, Choice, Vote
from .forms import PollForm, ChoiceFormSet, VoteForm
from .aws_utils import send_poll_notification, invoke_poll_notification_lambda

class IndexView(ListView):
    model = Poll
    template_name = 'voting_app/index.html'
    context_object_name = 'polls'
    
    def get_queryset(self):
        return Poll.objects.order_by('-created_at')

class PollListView(ListView):
    model = Poll
    template_name = 'voting_app/poll_list.html'
    context_object_name = 'polls'
    
    def get_queryset(self):
        return Poll.objects.order_by('-created_at')

class PollDetailView(DetailView):
    model = Poll
    template_name = 'voting_app/poll_detail.html'
    context_object_name = 'poll'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        poll = self.get_object()
        
        # Add vote form
        context['vote_form'] = VoteForm(poll=poll)
        
        # Get results
        choices = poll.choices.all()
        total_votes = sum(choice.votes.count() for choice in choices)
        results = []
        
        for choice in choices:
            votes_count = choice.votes.count()
            percentage = (votes_count / total_votes * 100) if total_votes > 0 else 0
            results.append({
                'text': choice.text,
                'votes': votes_count,
                'percentage': round(percentage, 1)
            })
        
        context['results'] = results
        context['is_active'] = poll.is_active()
        context['total_votes'] = total_votes
        
        return context
    
    def post(self, request, *args, **kwargs):
        poll = self.get_object()
        
        if not poll.is_active():
            messages.error(request, "This poll has ended")
            return HttpResponseRedirect(self.request.path)
        
        form = VoteForm(poll, request.POST)
        if form.is_valid():
            try:
                vote = form.save(commit=False)
                vote.save()
                messages.success(request, "Your vote has been recorded!")
            except IntegrityError:
                messages.error(request, "You have already voted in this poll!")
            
            return HttpResponseRedirect(self.request.path)
        else:
            messages.error(request, "There was an error with your vote.")
            return self.get(request, *args, **kwargs)

class PollCreateView(CreateView):
    model = Poll
    form_class = PollForm
    template_name = 'voting_app/poll_create.html'
    success_url = reverse_lazy('poll_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['choices'] = ChoiceFormSet(self.request.POST, self.request.FILES)
        else:
            context['choices'] = ChoiceFormSet()
        return context

    def form_valid(self, form):
        # Log all FILES received
        logger.info(f"Received FILES: {self.request.FILES}")
        
        context = self.get_context_data()
        choices = context['choices']
        
        # Save the poll
        self.object = form.save(commit=False)
        
        # Handle image upload - use FILES directly
        image = self.request.FILES.get('poll_image')
        logger.info(f"Image from FILES: {image}")
        
        if image:
            try:
                # Save image to S3
                logger.info(f"Attempting to save image: {image.name}")
                image_saved = self.object.save_poll_image(image)
                logger.info(f"Image save result: {image_saved}")
                
                if not image_saved:
                    messages.error(self.request, "Failed to upload poll image")
                    return self.render_to_response(self.get_context_data(form=form))
            except Exception as e:
                logger.error(f"Image upload error: {e}", exc_info=True)
                messages.error(self.request, f"Image upload failed: {str(e)}")
                return self.render_to_response(self.get_context_data(form=form))
        
        # Complete poll save
        self.object.save()

        if choices.is_valid():
            choices.instance = self.object
            choices.save()
            
            # Send AWS notifications
            try:
                send_poll_notification(self.object)
                invoke_poll_notification_lambda(self.object)
                messages.success(self.request, "Poll created successfully! Notifications sent.")
            except Exception as e:
                messages.warning(self.request, f"Poll created, but notification failed: {str(e)}")
            
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))
        
        
class PollUpdateView(UpdateView):
    model = Poll
    form_class = PollForm
    template_name = 'voting_app/poll_update.html'
    success_url = reverse_lazy('poll_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['choices'] = ChoiceFormSet(
                self.request.POST, 
                self.request.FILES, 
                instance=self.object
            )
        else:
            context['choices'] = ChoiceFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        choices = context['choices']
        
        self.object = form.save()
        
        if choices.is_valid():
            choices.instance = self.object
            choices.save()
            
            messages.success(self.request, "Poll updated successfully!")
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))
        


class PollDeleteView(DeleteView):
    model = Poll
    template_name = 'voting_app/poll_delete.html'
    success_url = reverse_lazy('poll_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "Poll deleted successfully!")
        return super().delete(request, *args, **kwargs)

# Create your views here.
