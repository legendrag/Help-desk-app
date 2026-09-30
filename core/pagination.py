from django.core.paginator import Paginator
from django.utils.functional import cached_property


class KnownCountPaginator(Paginator):
    """Reuse a count already computed for an ETag instead of scanning again."""

    def __init__(
        self,
        object_list,
        per_page,
        orphans=0,
        allow_empty_first_page=True,
        known_count=None,
    ):
        self.known_count = known_count
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)

    @cached_property
    def count(self):
        if self.known_count is not None:
            return self.known_count
        return self.object_list.count()
