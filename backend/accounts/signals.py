from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User


@receiver(post_save, sender=User)
def create_personal_workspace(sender, instance, created, **kwargs):
    if created:
        from workspaces.services import ensure_personal_workspace

        ensure_personal_workspace(instance)
