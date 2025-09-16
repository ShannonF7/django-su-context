from django.core.management.base import BaseCommand
from feedback_app.models import Feedback, ChangeLog, DocumentTask


class Command(BaseCommand):
    help = 'Updates the "state" field to 1 for three models: Feedback, ChangeLog, and DocumentTask.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting state update task..."))

        updated_feedback_count = Feedback.objects.update(state=1)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {updated_feedback_count} Feedback records."
            )
        )

        updated_changelog_count = ChangeLog.objects.update(state=1)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {updated_changelog_count} ChangeLog records."
            )
        )

        updated_documenttask_count = DocumentTask.objects.update(state=1)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {updated_documenttask_count} DocumentTask records."
            )
        )

        self.stdout.write(self.style.SUCCESS("State update task finished."))
