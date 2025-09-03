# Generated manually to migrate EDITOR roles to MEMBER

from django.db import migrations

def migrate_editor_to_member(apps, schema_editor):
    """Convert all EDITOR roles to MEMBER"""
    ProjectMember = apps.get_model('project', 'ProjectMember')
    ProjectInvitation = apps.get_model('project', 'ProjectInvitation')
    
    # Update ProjectMember roles
    ProjectMember.objects.filter(role='EDITOR').update(role='MEMBER')
    ProjectMember.objects.filter(role='VIEWER').update(role='MEMBER')
    
    # Update ProjectInvitation roles
    ProjectInvitation.objects.filter(role='EDITOR').update(role='MEMBER')
    ProjectInvitation.objects.filter(role='VIEWER').update(role='MEMBER')

def reverse_migration(apps, schema_editor):
    """Reverse migration - convert MEMBER back to EDITOR"""
    ProjectMember = apps.get_model('project', 'ProjectMember')
    ProjectInvitation = apps.get_model('project', 'ProjectInvitation')
    
    # Can't distinguish which were EDITOR vs VIEWER, so make all EDITOR
    ProjectMember.objects.filter(role='MEMBER').update(role='EDITOR')
    ProjectInvitation.objects.filter(role='MEMBER').update(role='EDITOR')

class Migration(migrations.Migration):

    dependencies = [
        ('project', '0003_alter_projectinvitation_role_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_editor_to_member, reverse_migration),
    ]