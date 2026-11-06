from django.contrib import admin
from .models import ProcessedFile


@admin.register(ProcessedFile)
class ProcessedFileAdmin(admin.ModelAdmin):
    list_display = ("id", "tool", "original_name", "created_at")
    list_filter = ("tool", "created_at")
    search_fields = ("original_name",)
    readonly_fields = ("tool", "original_name", "output_file", "created_at", "session_key")
