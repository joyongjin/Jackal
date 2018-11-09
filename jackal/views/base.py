from rest_framework.response import Response
from rest_framework.views import APIView

from jackal.filters import JackalQueryFilter
from jackal.helpers.dict_helper import JackalDictMapper
from jackal.inspectors import BaseInspector
from jackal.settings import jackal_settings


class _Response:
    def success(self, detail='success', **kwargs):
        return Response({'detail': detail, **kwargs})

    def simple_response(self, result=None, status=200, headers=None, **kwargs):
        return Response(result, status=status, headers=headers, **kwargs)

    def bad_request(self, **data):
        return Response(data, status=400)

    def forbidden(self, **data):
        return Response(data, status=403)

    def internal_server_error(self, **data):
        return Response(data, status=500)


class _Getter:
    def get_queryset(self):
        return self.queryset

    def get_model(self):
        if self.model is not None:
            return self.model
        else:
            return self.get_queryset().model

    def get_lookup_map(self, **additional):
        d = self.lookup_map
        return {**d, **additional}

    def get_filter_map(self, **additional):
        d = self.filter_map
        return {**d, **additional}

    def get_extra_kwargs(self, **additional):
        d = self.extra_kwargs
        return {**d, **additional}

    def get_query_filter_class(self, ):
        if self.query_filter is None:
            return JackalQueryFilter
        return self.query_filter

    def get_serializer_class(self, ):
        return self.serializer_class

    def get_serializer_context(self):
        return {}

    def get_jackal_exception_handler(self, ):
        return jackal_settings.EXCEPTION_HANDLER

    def get_inspector(self, request):
        inspect_map = self.get_cur_inspect_map()
        if not inspect_map:
            return None
        ins_class = self.inspector_class
        return ins_class(request.data, inspect_map)

    def get_cur_inspect_map(self):
        return getattr(self, '{}_inspect_map'.format(self.request.method), self.inspect_map)

    def get_inspected_data(self, request):
        inspector = self.get_inspector(request)
        if inspector is not None:
            request.is_inspected = True
            return inspector.inspected_data
        else:
            request.is_inspected = False
            if hasattr(request.data, 'dict'):
                return request.data.dict()
            else:
                return request.data

    def get_user_field(self):
        return self.user_field


class _PrePost:
    def pre_method_call(self, request, *args, **kwargs):
        """
        This will call before method run. Likes get, post, patch...
        """
        pass

    def post_method_call(self, request, response, *args, **kwargs):
        """
        This will call after method run. Likes get, post, patch...
        """
        pass

    def pre_dispatch(self, request, *args, **kwargs):
        """
        This will call before dispatch. before permission check, before authenticate, before initial request...
        """
        pass

    def post_dispatch(self, request, response, *args, **kwargs):
        """
        This will call after dispatch. after all api view logic. So it receive response to argument.
        """
        pass

    def pre_check_permissions(self, request):
        pass

    def post_check_permissions(self, request):
        pass

    def pre_check_object_permissions(self, request, obj):
        pass

    def post_check_object_permissions(self, request, obj):
        pass


class JackalBaseAPIView(APIView, _Getter, _PrePost, _Response):
    default_permission_classes = ()
    default_authentication_classes = ()
    permission_classes = ()
    authentication_classes = ()

    model = None
    queryset = None

    lookup_map = {}
    filter_map = {}
    search_dict = {}
    extra_kwargs = {}
    inspect_map = {}
    user_field = ''

    serializer_class = None
    query_filter = JackalQueryFilter
    inspector_class = BaseInspector

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.permission_classes += self.default_permission_classes
        self.authentication_classes += self.default_authentication_classes

    def dispatch(self, request, *args, **kwargs):
        self.pre_dispatch(request, *args, **kwargs)
        response = super().dispatch(request, *args, **kwargs)
        self.post_dispatch(request, response, *args, **kwargs)
        return response

    def handle_exception(self, exc):
        """
        high jacking exception and handle with jackal_exception_handler
        """
        jackal_handler = self.get_jackal_exception_handler()
        context = self.get_exception_handler_context()
        response = jackal_handler(exc, context)
        if response is not None:
            response.exception = True
            return response
        else:
            return super().handle_exception(exc)

    def initialize_request(self, request, *args, **kwargs):
        request = super().initialize_request(request, *args, **kwargs)
        request.inspected_data = self.get_inspected_data(request)
        return request

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.pre_method_call(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        super().post_method_call(request, response, *args, **kwargs)
        return super().finalize_response(request, response, *args, **kwargs)

    def check_permissions(self, request):
        self.pre_check_permissions(request)
        super().check_permissions(request)
        self.post_check_permissions(request)

    def check_object_permissions(self, request, obj):
        self.pre_check_object_permissions(request, obj)
        super().check_object_permissions(request, obj)
        self.post_check_object_permissions(request, obj)

    def get_object(self, request, **kwargs):
        queryset = self.get_user_queryset(self.get_model().objects.all(), request)

        f_class = self.get_query_filter_class()
        f = f_class(queryset=queryset, params=request.query_params)

        lookup_map = self.get_lookup_map()
        extra_kwargs = self.get_extra_kwargs(**JackalDictMapper.av2bv(lookup_map, kwargs))

        obj = f.extra(**extra_kwargs).get(raise_404=True)
        self.check_object_permissions(request=request, obj=obj)
        return obj

    def get_filtered_queryset(self, request, **kwargs):
        queryset = self.get_user_queryset(self.get_queryset(), request)

        f_class = self.get_query_filter_class()
        f = f_class(queryset=queryset, params=request.query_params)

        lookup_map = self.get_lookup_map()
        filter_map = self.get_filter_map()
        extra_kwargs = self.get_extra_kwargs()
        extra_kwargs.update(JackalDictMapper.av2bv(lookup_map, kwargs))

        queryset = f.filter_map(filter_map).extra(**extra_kwargs).queryset
        return queryset

    def get_user_queryset(self, queryset, request):
        user_field = self.get_user_field()
        if user_field:
            queryset = queryset.filter(**{user_field: request.user})

        return queryset


class JackalAPIView(JackalBaseAPIView):
    pass
