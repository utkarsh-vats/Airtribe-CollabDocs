from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Document, AuditLog

@receiver(post_save, sender=Document)
def log_document_changes(sender, instance, **kwargs):
    action = 'CREATED' if instance._state.adding else 'UPDATED'
    AuditLog.objects.create(
        actor=instance.created_by,
        action=action,
        model_name='Document',
        object_id=instance.id,
    )