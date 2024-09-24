from flask import Blueprint, request
from markupsafe import escape as escape_html

from decorators.api_endpoint_decorator import (
    api_endpoint,
    ApiEndpointUserGroup,
    ApiEndpointAction,
)
from models.main import User
from services.admin import admin_segment_service
from services import outlier_service

app_admin_segment = Blueprint("app_admin_segment", __name__)


@app_admin_segment.route("/admin/segments", methods=["POST"])
@api_endpoint(
    user_group=ApiEndpointUserGroup.MAINTAINER, action=ApiEndpointAction.WRITE
)
def upsert_segment(user_context: User):
    data = request.get_json()

    admin_segment_service.upsert_segment(
        id_segment=data.get("idSegment", None),
        description=data.get("description", None),
        active=data.get("active", None),
        user=user_context,
    )

    return escape_html(data.get("idSegment"))


@app_admin_segment.route(
    "/admin/segments/departments/<int:id_segment>", methods=["GET"]
)
@api_endpoint(user_group=ApiEndpointUserGroup.MAINTAINER, action=ApiEndpointAction.READ)
def get_departments(id_segment):
    return admin_segment_service.get_departments(id_segment)


@app_admin_segment.route("/admin/segments/departments", methods=["POST"])
@api_endpoint(
    user_group=ApiEndpointUserGroup.MAINTAINER, action=ApiEndpointAction.WRITE
)
def upsert_department(user_context: User):
    data = request.get_json()

    admin_segment_service.update_segment_departments(
        id_segment=data.get("idSegment", None),
        department_list=data.get("departmentList", None),
        user=user_context,
    )

    return escape_html(data.get("idSegment"))


@app_admin_segment.route("/admin/segments/outliers/process-list", methods=["POST"])
@api_endpoint(
    user_group=ApiEndpointUserGroup.MAINTAINER, action=ApiEndpointAction.WRITE
)
def get_outliers_process_list(user_context: User):
    data = request.get_json()

    return outlier_service.get_outliers_process_list(
        id_segment=data.get("idSegment", None),
        user=user_context,
    )
