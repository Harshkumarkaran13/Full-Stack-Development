from django.db import models


class ProcessedFile(models.Model):
    tool = models.CharField(max_length=40)
    original_name = models.CharField(max_length=255, blank=True)
    output_file = models.FileField(upload_to="processed/")
    created_at = models.DateTimeField(auto_now_add=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)

    def __str__(self):
        return f"{self.tool}: {self.original_name}"
