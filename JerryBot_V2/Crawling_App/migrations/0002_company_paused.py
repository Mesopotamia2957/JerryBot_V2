from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Crawling_App', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='paused',
            field=models.BooleanField(default=False, help_text='켜면 배치 크롤링에서 제외한다. 기존 공고는 유지된다.', verbose_name='일시 중지'),
        ),
    ]
