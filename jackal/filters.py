from django.db.models import Q

from jackal.exceptions import NotFound
from jackal.loaders import query_function_loader
from jackal.shortcuts import iterable


class RequestFilterMixin:
    @staticmethod
    def get_q_object(key, *filter_keywords):
        q_object = Q()
        for q in filter_keywords:
            q_object |= Q(**{q: key})
        return q_object

    @staticmethod
    def get_query_function(key):
        for n, callback in query_function_loader().items():
            if key.find(n) >= 0:
                return key.replace(n, ''), callback
        else:
            return key, None


class JackalQueryFilter(RequestFilterMixin):
    ordering_key = 'ordering'
    search_keyword_key = 'search_keyword'
    search_type_key = 'search_type'

    def __init__(self, queryset, params=None):
        self.queryset = queryset
        if params is None:
            params = {}
        self.params = params

    def filter_map(self, filter_map):
        """
        params = {
            'name': 'Yongjin',
            'age_lowest': '20',
        }
        f = JackalQueryFilter(User.objects.all(), params)

        queryset = f.filter_map({
            'name': 'name__contains',
            'age_lowest': 'age__gte'
        }).queryset
        """

        queryset = self.queryset

        filterable = {}
        filterable_q_objects = list()
        for map_key, filter_keyword in filter_map.items():
            map_key, callback = self.get_query_function(map_key)
            param_value = self.params.get(map_key)

            if param_value in [None, '']:
                continue
            elif callback is not None:
                param_value = callback(param_value)

            if iterable(filter_keyword):
                filterable_q_objects.append(self.get_q_object(param_value, *filter_keyword))
            else:
                filterable[filter_keyword] = param_value

        self.queryset = queryset.filter(*filterable_q_objects, **filterable).distinct()
        return self

    def search(self, search_dict):
        """
        """
        queryset = self.queryset

        search_keyword = self.params.get(self.search_keyword_key)
        search_type = self.params.get(self.search_type_key, 'all')

        dict_value = search_dict.get(search_type, None)

        if dict_value is not None and search_keyword is not None:
            if iterable(dict_value):
                self.queryset = queryset.filter(self.get_q_object(search_keyword, *dict_value))
            else:
                self.queryset = queryset.filter(**{dict_value: search_keyword})
        return self

    def extra(self, **extra_kwargs):
        """
        """
        queryset = self.queryset
        self.queryset = queryset.filter(**extra_kwargs)
        return self

    def ordering(self):
        """
        """
        ordering = self.params.get(self.ordering_key)
        if ordering:
            queryset = self.queryset
            order_by = ordering.split(',')
            self.queryset = queryset.order_by(*order_by)
        return self

    def get(self, raise_404=False, **kwargs):
        """
        """
        queryset = self.queryset
        obj = self.queryset.filter(**kwargs).first()
        if obj is None and raise_404:
            raise NotFound(model=queryset.model, filters=kwargs)

        return obj
