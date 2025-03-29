from django.contrib import admin
from .models import Poll, Choice, Vote

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 3

class PollAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]
    list_display = ('title', 'created_at', 'end_date', 'is_active')
    search_fields = ['title', 'description']

admin.site.register(Poll, PollAdmin)
admin.site.register(Vote)

# Register your models here.
