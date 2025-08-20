# Tasks are automatically discovered by Celery's autodiscover_tasks()
# Avoid eager imports to prevent Django model loading issues
default_app_config = 'tasks.apps.TasksConfig'