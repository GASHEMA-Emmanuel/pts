from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0002_contract_extensions_and_completion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── New budget, supplier, and structure fields ─────────────
        migrations.AddField(
            model_name='contract',
            name='contract_budget',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=18, null=True,
                help_text='Contract amount in RWF.',
            ),
        ),
        migrations.AddField(
            model_name='contract',
            name='supplier_name',
            field=models.CharField(
                blank=True, max_length=500,
                help_text='Supplier / contractor name (or Consultant name for Consultancy types).',
            ),
        ),
        migrations.AddField(
            model_name='contract',
            name='contract_structure',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[('Lumpsum', 'Lumpsum'), ('Framework', 'Framework')],
                help_text='Lumpsum or Framework — the payment structure for Consultancy/Works contracts.',
            ),
        ),

        # ── Replace project_manager FK with project_managers M2M ──
        migrations.RemoveField(
            model_name='contract',
            name='project_manager',
        ),
        migrations.AddField(
            model_name='contract',
            name='project_managers',
            field=models.ManyToManyField(
                blank=True,
                related_name='managed_contracts',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
