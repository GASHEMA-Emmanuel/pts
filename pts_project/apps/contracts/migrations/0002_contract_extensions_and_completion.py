from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0001_initial'),
    ]

    operations = [
        # ── Contract: new fields ────────────────────────────────────
        migrations.AddField(
            model_name='contract',
            name='lumpsum_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='contract',
            name='original_delivery_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='contract',
            name='extension_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='contract',
            name='extension_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='contract',
            name='completion_comment',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='contract',
            name='performance_guarantee',
            field=models.TextField(blank=True),
        ),
        # ── PurchaseOrder: new fields ───────────────────────────────
        migrations.AddField(
            model_name='purchaseorder',
            name='original_delivery_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='extension_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='extension_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='completion_comment',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='purchaseorder',
            name='performance_guarantee',
            field=models.TextField(blank=True),
        ),
    ]
