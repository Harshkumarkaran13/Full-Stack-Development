from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("tool/<slug:tool>/", views.tool_page, name="tool"),
    path("process/<slug:tool>/", views.process_tool, name="process_tool"),
    path("api/bootstrap/", views.api_bootstrap, name="api_bootstrap"),
    path("api/history/", views.api_history, name="api_history"),
    path("api/process/<slug:tool>/", views.api_process_tool, name="api_process_tool"),
    path("download/<int:file_id>/", views.download_file, name="download_file"),
    path("history/", views.history, name="history"),
]
