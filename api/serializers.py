from typing import Any

from .models import User, Workspace, WorkspaceMember, Document, DocumentVersion, Comment, Tag, AuditLog
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")
        if not any(c.isupper() for c in value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain at least one digit.")
        return value
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class WorkspaceSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ['id', 'name', 'owner', 'member_count', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        return obj.members.count()
    
    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Workspace name cannot be empty.")
        return value

class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True
    )
    role = serializers.ChoiceField(choices=WorkspaceMember.Roles.choices)

    class Meta:
        model = WorkspaceMember
        fields = ['id', 'workspace', 'user', 'user_id', 'role', 'joined_at', 'updated_at']
        read_only_fields = ['id', 'joined_at', 'updated_at']

class DocumentSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    created_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='created_by',
        write_only=True
    )

    # tags = TagSerializer(many=True, read_only=True)
    tags = serializers.StringRelatedField(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        source='tags',
        write_only=True,
        required=False,
        allow_null=True
    )

    version_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ['id', 'title', 'content', 'workspace', 'tags', 'tag_ids', 'created_by', 'created_by_id', 'status', 'version_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_version_count(self, obj):
        return obj.versions.count()
    
class DocumentVersionSerializer(serializers.ModelSerializer):
    saved_by = UserSerializer(read_only=True)
    saved_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='saved_by',
        write_only=True,
        # required=False,
        # allow_null=True
    )

    class Meta:
        model = DocumentVersion
        fields = ['id', 'document', 'title', 'content', 'version_number', 'saved_by', 'saved_by_id', 'saved_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'saved_at', 'created_at', 'updated_at']

class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='author',
        write_only=True
    )
    # parent = serializers.PrimaryKeyRelatedField(
    #     queryset=Comment.objects.all(),
    #     source='parent',
    #     required=False,
    #     allow_null=True,
    #     write_only=True
    # )

    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'document', 'author', 'author_id', 'content', 'parent', 'replies', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_replies(self, obj):
        replies = obj.replies.all()
        return CommentSerializer(replies, many=True).data

class TagSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ['id', 'name', 'document_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_document_count(self, obj):
        return obj.documents.count()

class AuditLogSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'action', 'model_name', 'object_id', 'changes', 'timestamp']