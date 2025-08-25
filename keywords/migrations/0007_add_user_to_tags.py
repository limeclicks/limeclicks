# Migration to add user field to tags

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_tags_to_first_user(apps, schema_editor):
    """Assign all existing tags to the first user"""
    Tag = apps.get_model('keywords', 'Tag')
    User = apps.get_model('accounts', 'User')
    
    # Get the first user
    first_user = User.objects.first()
    
    if first_user and Tag.objects.exists():
        # Update all existing tags to belong to the first user
        Tag.objects.update(user=first_user)


def reverse_assignment(apps, schema_editor):
    """Reverse function for rollback"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('keywords', '0006_add_tags_model'),
    ]

    operations = [
        # Add user field as nullable first
        migrations.AddField(
            model_name='tag',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text='User who owns this tag',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tags',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        
        # Assign existing tags to first user
        migrations.RunPython(assign_tags_to_first_user, reverse_assignment),
        
        # Make user field required
        migrations.AlterField(
            model_name='tag',
            name='user',
            field=models.ForeignKey(
                help_text='User who owns this tag',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tags',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        
        # Add new fields
        migrations.AddField(
            model_name='tag',
            name='description',
            field=models.TextField(blank=True, help_text='Optional description for this tag'),
        ),
        
        migrations.AddField(
            model_name='tag',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Whether this tag is active'),
        ),
        
        migrations.AddField(
            model_name='tag',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        
        # Remove old unique constraint and add new one
        migrations.AlterField(
            model_name='tag',
            name='name',
            field=models.CharField(db_index=True, max_length=50),
        ),
        
        migrations.AlterUniqueTogether(
            name='tag',
            unique_together={('user', 'name')},
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='tag',
            index=models.Index(fields=['user', 'is_active'], name='keywords_ta_user_id_is_act_idx'),
        ),
        
        migrations.AddIndex(
            model_name='tag',
            index=models.Index(fields=['user', 'slug'], name='keywords_ta_user_id_slug_idx'),
        ),
    ]