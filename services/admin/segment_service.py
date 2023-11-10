from flask_api import status

from models.main import *
from models.appendix import *
from models.segment import *
from models.enums import RoleEnum

from exception.validation_error import ValidationError


def get_departments(id_segment):
    sd = db.aliased(SegmentDepartment)
    q_department = (
        db.session.query(func.count(sd.id).label("count"))
        .select_from(sd)
        .filter(sd.idHospital == Department.idHospital)
        .filter(sd.idDepartment == Department.id)
        .filter(sd.id != id_segment)
    )

    departments = (
        db.session.query(
            Department,
            Hospital,
            SegmentDepartment,
            q_department.as_scalar().label("total"),
        )
        .join(Hospital, Department.idHospital == Hospital.id)
        .outerjoin(
            SegmentDepartment,
            and_(
                SegmentDepartment.idDepartment == Department.id,
                SegmentDepartment.idHospital == Department.idHospital,
                SegmentDepartment.id == id_segment,
            ),
        )
        .order_by(asc(Department.name))
        .all()
    )

    deps = []
    for d in departments:
        deps.append(
            {
                "idHospital": d[0].idHospital,
                "hospitalName": d[1].name,
                "idDepartment": d[0].id,
                "name": d[0].name,
                "checked": d[2] is not None,
                "uses": d[3],
            }
        )

    return deps


def update_segment_departments(id_segment, department_list, user):
    roles = user.config["roles"] if user.config and "roles" in user.config else []
    if RoleEnum.ADMIN.value not in roles and RoleEnum.TRAINING.value not in roles:
        raise ValidationError(
            "Usuário não autorizado",
            "errors.unauthorizedUser",
            status.HTTP_401_UNAUTHORIZED,
        )

    if id_segment == None:
        raise ValidationError(
            "Parâmetro inválido", "errors.invalidParam", status.HTTP_400_BAD_REQUEST
        )

    db.session.query(SegmentDepartment).filter(
        SegmentDepartment.id == id_segment
    ).delete()

    for d in department_list:
        if d["idHospital"] == None or d["idDepartment"] == None:
            raise ValidationError(
                "Parâmetro inválido", "errors.invalidParam", status.HTTP_400_BAD_REQUEST
            )

        sd = SegmentDepartment()
        sd.id = id_segment
        sd.idHospital = d["idHospital"]
        sd.idDepartment = d["idDepartment"]

        db.session.add(sd)
