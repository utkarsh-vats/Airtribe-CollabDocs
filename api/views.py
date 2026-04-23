from django.db.models.query import QuerySet
from rest_framework.serializers import BaseSerializer
from .models import *
from .serializers import *
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction, IntegrityError
from django.db.models import Count, Q
from rest_framework.response import Response
from rest_framework.decorators import action

# User
# POST api/users/
# GET api/users/
# GET api/users/{id}
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    http_method_names = ['get', 'post']

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.action == 'create':
            return UserRegistrationSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    
# Workspace
# POST /api/workspaces/	            - Create workspace
# GET api/workspaces/	            - List workspaces
# GET /api/workspaces/{id}/	        - GET Detail
# GET api/workspaces/{id}/stats/    - @action — aggregate stats
class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.select_related('owner')
    serializer_class = WorkspaceSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            workspace = serializer.save(owner=self.request.user)
            WorkspaceMember.objects.create(
                workspace=workspace,
                user=self.request.user,
                role=WorkspaceMember.Roles.ADMIN
            )
            AuditLog.objects.create(
                actor=workspace.owner,
                action=AuditLog.Actions.CREATED,
                model_name='Workspace',
                object_id=workspace.id
            )

    @action(detail=True, methods=['get'])
    def stats(self, request, *args, **kwargs):
        workspace = self.get_object()
        stats = {
            'total_documents': workspace.documents.count(),
            'total_members': workspace.members.count(),
            'document_by_status': workspace.documents.values('status').annotate(count=Count('id')),
        }
        return Response(stats)
    
    @action(detail=True, methods=['get', 'post'])
    def members(self, request, *args, **kwargs):
        workspace = self.get_object()
        if request.method == 'GET':
            members = workspace.members.select_related('user')
            serializer = WorkspaceMemberSerializer(members, many=True)
            return Response(serializer.data)
        serializer = WorkspaceMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(workspace=workspace)
        except IntegrityError:
            return Response(
                {
                    'error': 'User is already a member of this workspace.'
                }, 
                status=status.HTTP_409_CONFLICT
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# # Workspace Member
# # POST /api/workspaces/{id}/members/	- Add member (catch IntegrityError → 409)
# # GET /api/workspaces/{id}/members/	    - list members
# class WorkspaceMemberViewSet(viewsets.ModelViewSet):
#     queryset = WorkspaceMember.objects.all()
#     serializer_class = WorkspaceMemberSerializer

# Document
# POST /api/documents/	                - Create document
# GET api/documents/                    - List with filters
# GET api/documents/{id}/	            - Detail
# PUT/PATCH	/api/documents/{id}/		- Update document
# GET /api/documents/{id}/versions/	    - @action — list versions
# GET /api/documents/{id}/stats/        - @action - stats {version_count, comment_count, contributor_count}
# POST /api/documents/{id}/tags/        - @action - ManyToMany - add tags
class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related('created_by', 'workspace').prefetch_related('tags')
    serializer_class = DocumentSerializer

    def perform_create(self, serializer) -> None:
        with transaction.atomic():
            document = serializer.save(created_by=self.request.user)
            DocumentVersion.objects.create(
                document=document,
                title=document.title,
                content=document.content,
                version_number=1,
                saved_by=document.created_by
            )
    
    def perform_update(self, serializer) -> None:
        with transaction.atomic():
            document = serializer.save()
            DocumentVersion.objects.create(
                document=document,
                title=document.title,
                content=document.content,
                version_number=document.versions.count() + 1,
                saved_by=document.created_by
            )

    def get_queryset(self) -> QuerySet:
        queryset = Document.objects.select_related('created_by', 'workspace').prefetch_related('tags')
        workspace = self.request.query_params.get('workspace')
        if workspace:
            queryset = queryset.filter(workspace_id=workspace)
        doc_status = self.request.query_params.get('status')
        if doc_status:
            queryset = queryset.filter(status=doc_status)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(content__icontains=search))
        created_after = self.request.query_params.get('created_after')
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        created_before = self.request.query_params.get('created_before')
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        return queryset
    
    @action(detail=True, methods=['get'])
    def versions(self, request, *args, **kwargs) -> Response:
        document = self.get_object()
        versions = document.versions.select_related('saved_by').order_by('-version_number')
        serializer = DocumentVersionSerializer(versions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, *args, **kwargs) -> Response:
        document = self.get_object()
        stats = {
            'version_count': document.versions.count(),
            'comment_count': document.comments.count(),
            'contributor_count': document.versions.values('saved_by').distinct().count(),
        }
        return Response(stats)

    @action(detail=False, methods=['get'])
    def summary(self, request, *args, **kwargs) -> Response:
        summary = Document.objects.aggregate(
            total=Count('id'),
            drafts=Count('id', filter=Q(status=Document.Statuses.DRAFT)),
            published=Count('id', filter=Q(status=Document.Statuses.PUBLISHED)),
            archived=Count('id', filter=Q(status=Document.Statuses.ARCHIVED)),

        )
        return Response(summary)
    
    @action(detail=True, methods=['post'])
    def tags(self, request, *args, **kwargs) -> Response:
        document = self.get_object()
        tag_ids = request.data.get('tag_ids', [])
        tags = Tag.objects.filter(id__in=tag_ids)
        document.tags.add(*tags)
        return Response({
            'status': 'tags added',
            'tags': list(tags.values_list('name', flat=True))
        })

# # Document Version
# class DocumentVersionViewSet(viewsets.ModelViewSet):
#     queryset = DocumentVersion.objects.all()
#     serializer_class = DocumentVersionSerializer

# Comment
# POST /api/comments/               - add comment
# GET /api/comments/?document={id}  - list all comments for document
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.select_related('author', 'document')
    serializer_class = CommentSerializer
    http_method_names = ['get', 'post']

    # def perform_create(self, serializer):
    #     serializer.save(author=self.request.user)

    def get_queryset(self) -> QuerySet:
        queryset = Comment.objects.select_related('author', 'document')
        document_id = self.request.query_params.get('document')
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        queryset = queryset.filter(parent=None)
        return queryset

# Tag
# POST /api/tags/           - create a tag
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.annotate(document_count=Count('documents'))
    serializer_class = TagSerializer

    def get_queryset(self) -> QuerySet:
        queryset = Tag.objects.annotate(document_count=Count('documents'))
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name)
        return queryset

# Audit Log
# GET /api/audit-logs/      - list audit logs
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('actor')
    serializer_class = AuditLogSerializer

    def get_queryset(self) -> QuerySet:
        queryset = AuditLog.objects.select_related('actor')
        object_id = self.request.query_params.get('object_id')
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        return queryset

