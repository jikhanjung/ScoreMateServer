from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tasks'
    
    def ready(self):
        """Import tasks when the app is ready"""
        try:
            # Import tasks to register them with Celery
            from . import pdf_tasks
            from . import file_tasks
            print("✓ Tasks imported successfully in ready()")
        except Exception as e:
            print(f"✗ Failed to import tasks in ready(): {e}")
