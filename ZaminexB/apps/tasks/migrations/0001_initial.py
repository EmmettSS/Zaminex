
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('properties', '0003_propertyimage'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Brief title of the task', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Detailed description of the task')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')], db_index=True, default='PENDING', max_length=20)),
                ('priority', models.CharField(choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('URGENT', 'Urgent')], default='MEDIUM', max_length=20)),
                ('task_type', models.CharField(choices=[('VIEWING', 'Viewing'), ('DOCUMENT', 'Document'), ('NEGOTIATION', 'Negotiation'), ('FOLLOW_UP', 'Follow-Up'), ('ADMINISTRATIVE', 'Administrative'), ('SITE_VISIT', 'Site Visit'), ('CONTRACT', 'Contract'), ('INSPECTION', 'Inspection')], default='VIEWING', max_length=20)),
                ('due_date', models.DateField(help_text='When the task should be completed')),
                ('completed_at', models.DateTimeField(blank=True, help_text='When the task was marked completed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(blank=True, help_text='Consultant assigned to this task', limit_choices_to={'role': 'AGENT'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_tasks', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(help_text='Admin or consultant who created the task', on_delete=django.db.models.deletion.PROTECT, related_name='created_tasks', to=settings.AUTH_USER_MODEL)),
                ('property', models.ForeignKey(blank=True, help_text='Property related to this task (optional)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='properties.property')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['assigned_to', 'status'], name='tasks_task_assigne_b3b2bc_idx'), models.Index(fields=['due_date', 'status'], name='tasks_task_due_dat_3f7773_idx')],
            },
        ),
    ]
