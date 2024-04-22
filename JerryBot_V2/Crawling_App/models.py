from django.db import models

class JobPost(models.Model):
    title = models.CharField(max_length=255)
    link = models.URLField()
    keywords = models.CharField(max_length=255)

    def __str__(self):
        return self.title
