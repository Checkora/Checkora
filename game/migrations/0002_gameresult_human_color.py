from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='gameresult',
            name='human_color',
            field=models.CharField(
                blank=True,
                choices=[('white', 'White'), ('black', 'Black')],
                max_length=10,
                null=True,
            ),
        ),
    ]
