from django.apps import AppConfig


class AClassroomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'a_classroom'

    def ready(self):
        import a_classroom.signals
