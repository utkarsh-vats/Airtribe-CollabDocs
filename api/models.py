from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

# Base Model
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# User
class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=15, blank=True, default="")

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"


# Workspace
class Workspace(BaseModel):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_workspaces')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.owner}"

# Workspace Member
class WorkspaceMember(BaseModel):
    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        EDITOR = 'EDITOR', 'Editor'
        VIEWER = 'VIEWER', 'Viewer'

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=Roles.choices, default=Roles.VIEWER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'user'], 
                name='unique_workspace_member'
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.workspace.name} - {self.role}"

# Document
class Document(BaseModel):
    class Statuses(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'
        ARCHIVED = 'ARCHIVED', 'Archived'

    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default="")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=10, choices=Statuses.choices, default=Statuses.DRAFT)

    def __str__(self):
        return f"{self.title}({self.status}) - {self.workspace}"

# Document Version
class DocumentVersion(BaseModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    title = models.CharField(max_length=255)    # snapshot of title at save time
    content = models.TextField(blank=True, default="")    # snapshot of content at save time
    version_number = models.PositiveIntegerField()
    saved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='document_versions')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.document.title} - Version {self.version_number}"

# Comment
class Comment(BaseModel):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='comments')
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author.username} on {self.document.title}"

# Tag
class Tag(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    documents = models.ManyToManyField(Document, related_name='tags', blank=True)

    def __str__(self):
        return self.name

# Audit Log
class AuditLog(BaseModel):
    class Actions(models.TextChoices):
        CREATED = 'CREATED', 'Created'
        UPDATED = 'UPDATED', 'Updated'
        DELETED = 'DELETED', 'Deleted'
        SHARED = 'SHARED', 'Shared'
        UNSHARED = 'UNSHARED', 'Unshared'
        ARCHIVED = 'ARCHIVED', 'Archived'
        UNARCHIVED = 'UNARCHIVED', 'Unarchived'
        COMMENTED = 'COMMENTED', 'Commented'
        UNCOMMENTED = 'UNCOMMENTED', 'Uncommented'
        TAGGED = 'TAGGED', 'Tagged'
        UNTAGGED = 'UNTAGGED', 'Untagged'

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=Actions.choices)
    model_name = models.CharField(max_length=100)
    object_id = models.UUIDField()
    changes = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.actor.username} - {self.action} - {self.model_name} - ({self.object_id})"