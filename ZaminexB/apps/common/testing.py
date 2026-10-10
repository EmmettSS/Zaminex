from django.core.cache import cache


class CacheClearingMixin:
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()
