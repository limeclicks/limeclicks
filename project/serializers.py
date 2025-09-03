from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Project, ProjectMember, ProjectInvitation, ProjectRole

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name']


class ProjectMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = ProjectMember
        fields = ['id', 'user', 'role', 'joined_at']


class ProjectInvitationSerializer(serializers.ModelSerializer):
    invited_by = UserSerializer(read_only=True)
    
    class Meta:
        model = ProjectInvitation
        fields = ['id', 'email', 'role', 'status', 'invited_by', 'created_at', 'expires_at']
        read_only_fields = ['status', 'invited_by', 'created_at', 'expires_at']


class InviteUsersSerializer(serializers.Serializer):
    emails = serializers.ListField(
        child=serializers.EmailField(),
        allow_empty=False,
        max_length=50
    )
    role = serializers.ChoiceField(
        choices=ProjectRole.choices,
        default=ProjectRole.EDITOR
    )
    
    def validate_emails(self, value):
        return [email.lower() for email in value]


class UpdateMemberRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[ProjectRole.EDITOR, ProjectRole.VIEWER]
    )