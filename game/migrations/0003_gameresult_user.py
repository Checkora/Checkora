from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('game', '0002_add_missing_draw_end_reasons'),
    ]

    operations = [
        migrations.AddField(
            model_name='gameresult',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='game_results',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
