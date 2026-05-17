from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('game', '0004_gameresult_player_color'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX auth_user_email_ci_uniq ON auth_user (LOWER(email)) WHERE email != '';",
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_ci_uniq;"
        )
    ]
