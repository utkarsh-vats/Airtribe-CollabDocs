from rest_framework.serializers import BaseSerializer
from .models import *
from .serializers import *
from rest_framework.authtoken.models import Token
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
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# Workspace Member
class WorkspaceMemberViewSet(viewsets.ModelViewSet):
    queryset = WorkspaceMember.objects.all()
    serializer_class = WorkspaceMemberSerializer

# Document
class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# Document Version
class DocumentVersionViewSet(viewsets.ModelViewSet):
    queryset = DocumentVersion.objects.all()
    serializer_class = DocumentVersionSerializer

# Comment
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

# Tag
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

# Audit Log
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer

