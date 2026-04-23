from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Document, AuditLog

@receiver(post_save, sender=Document)
def log_document_changes(sender, instance, created, **kwargs):
    action = 'CREATED' if created else 'UPDATED'
    AuditLog.objects.create(
        actor=instance.created_by,
        action=action,
        model_name='Document',
        object_id=instance.id,
    )