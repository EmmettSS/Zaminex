from django.db import models


class AIInsightCache(models.Model):
    entity = models.CharField(max_length=20, verbose_name="موجودیت")
    entity_id = models.PositiveIntegerField(verbose_name="شناسه")
    fingerprint = models.CharField(max_length=64, verbose_name="اثر انگشت داده")
    payload = models.JSONField(verbose_name="خروجی مدل")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        db_table = "common_aiinsightcache"
        verbose_name = "کش تحلیل هوش مصنوعی"
        verbose_name_plural = "کش تحلیل هوش مصنوعی"
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "entity_id"], name="uniq_ai_insight_entity"
            ),
        ]

    def __str__(self):
        return f"{self.entity}:{self.entity_id}"
