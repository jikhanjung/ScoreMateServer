# Quota in fractional MB (was integer MB, floored per file: files under 1 MB counted as 0).
# Recompute every user's usage from the bytes of the versions they uploaded (plus legacy scores without versions).

from django.db import migrations, models

MB = 1024 * 1024


def recompute(apps, schema_editor):
    User = apps.get_model('core', 'User')
    Score = apps.get_model('scores', 'Score')
    ScoreVersion = apps.get_model('scores', 'ScoreVersion')
    usage = {}
    for uploaded_by, size in ScoreVersion.objects.exclude(uploaded_by=None).values_list('uploaded_by', 'size_bytes'):
        usage[uploaded_by] = usage.get(uploaded_by, 0) + (size or 0)
    for user_id, size in Score.objects.filter(versions__isnull=True).values_list('user', 'size_bytes'):
        usage[user_id] = usage.get(user_id, 0) + (size or 0)
    for user in User.objects.all():
        User.objects.filter(pk=user.pk).update(used_quota_mb=usage.get(user.pk, 0) / MB)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_social_account'),
        ('scores', '0006_score_arranger'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='used_quota_mb',
            field=models.FloatField(default=0),
        ),
        migrations.RunPython(recompute, migrations.RunPython.noop),
    ]
