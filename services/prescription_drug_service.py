from sqlalchemy import literal, and_, func, or_, asc, case
from datetime import datetime, date, timedelta

from models.main import db, User
from models.prescription import (
    Prescription,
    PrescriptionDrug,
    Drug,
    MeasureUnit,
    Frequency,
    Outlier,
    DrugAttributes,
)
from models.appendix import Notes
from services import (
    prescription_service,
    data_authorization_service,
)
from exception.validation_error import ValidationError
from decorators.has_permission_decorator import has_permission, Permission
from utils import status
from routes.utils import timeValue


@has_permission(Permission.READ_PRESCRIPTION)
def getPrescriptionDrug(idPrescriptionDrug):
    return (
        db.session.query(
            PrescriptionDrug,
            Drug,
            MeasureUnit,
            Frequency,
            literal("0"),
            func.coalesce(func.coalesce(Outlier.manualScore, Outlier.score), 4).label(
                "score"
            ),
            DrugAttributes,
            Notes.notes,
            Prescription.status,
            Prescription.expire,
        )
        .outerjoin(Outlier, Outlier.id == PrescriptionDrug.idOutlier)
        .outerjoin(Drug, Drug.id == PrescriptionDrug.idDrug)
        .outerjoin(Notes, Notes.idPrescriptionDrug == PrescriptionDrug.id)
        .outerjoin(Prescription, Prescription.id == PrescriptionDrug.idPrescription)
        .outerjoin(
            MeasureUnit,
            and_(
                MeasureUnit.id == PrescriptionDrug.idMeasureUnit,
                MeasureUnit.idHospital == Prescription.idHospital,
            ),
        )
        .outerjoin(
            Frequency,
            and_(
                Frequency.id == PrescriptionDrug.idFrequency,
                Frequency.idHospital == Prescription.idHospital,
            ),
        )
        .outerjoin(
            DrugAttributes,
            and_(
                DrugAttributes.idDrug == PrescriptionDrug.idDrug,
                DrugAttributes.idSegment == PrescriptionDrug.idSegment,
            ),
        )
        .filter(PrescriptionDrug.id == idPrescriptionDrug)
        .first()
    )


def count_drugs_by_prescription(
    prescription: Prescription, drug_types, user: User, parent_agg_date=None
):
    if prescription.agg:
        prescription_query = prescription_service.get_query_prescriptions_by_agg(
            agg_prescription=prescription, is_cpoe=user.cpoe(), only_id=True
        )

        q = (
            db.session.query(PrescriptionDrug)
            .filter(PrescriptionDrug.idPrescription.in_(prescription_query))
            .filter(PrescriptionDrug.source.in_(drug_types))
        )

        if user.cpoe():
            q = q.filter(
                or_(
                    PrescriptionDrug.suspendedDate == None,
                    func.date(PrescriptionDrug.suspendedDate)
                    >= func.date(prescription.date),
                )
            )

        return q.count()
    else:
        q = (
            db.session.query(PrescriptionDrug)
            .filter(PrescriptionDrug.idPrescription == prescription.id)
            .filter(PrescriptionDrug.source.in_(drug_types))
        )

        if user.cpoe():
            q = q.filter(
                or_(
                    PrescriptionDrug.suspendedDate == None,
                    func.date(PrescriptionDrug.suspendedDate)
                    >= func.date(parent_agg_date),
                )
            )

        return q.count()


@has_permission(Permission.WRITE_PRESCRIPTION)
def update_pd_form(pd_list, user_context: User):
    for pd in pd_list:
        drug = drug = (
            db.session.query(PrescriptionDrug).filter(PrescriptionDrug.id == pd).first()
        )
        if drug is None:
            raise ValidationError(
                "Prescrição inexistente",
                "errors.invalidRegister",
                status.HTTP_400_BAD_REQUEST,
            )

        if not data_authorization_service.has_segment_authorization(
            id_segment=drug.idSegment, user=user_context
        ):
            raise ValidationError(
                "Usuário não autorizado neste segmento",
                "errors.businessRules",
                status.HTTP_401_UNAUTHORIZED,
            )

        drug.form = pd_list[pd]
        drug.update = datetime.today()
        drug.user = user_context.id

        db.session.flush()


@has_permission(Permission.READ_PRESCRIPTION)
def prescriptionDrugToDTO(pd):
    pdWhiteList = bool(pd[6].whiteList) if pd[6] is not None else False

    return {
        "idPrescription": str(pd[0].idPrescription),
        "idPrescriptionDrug": str(pd[0].id),
        "idDrug": pd[0].idDrug,
        "drug": pd[1].name if pd[1] is not None else "Medicamento " + str(pd[0].idDrug),
        "dose": pd[0].dose,
        "measureUnit": {"value": pd[2].id, "label": pd[2].description} if pd[2] else "",
        "frequency": {"value": pd[3].id, "label": pd[3].description} if pd[3] else "",
        "dayFrequency": pd[0].frequency,
        "doseconv": pd[0].doseconv,
        "time": timeValue(pd[0].interval),
        "interval": pd[0].interval,
        "route": pd[0].route,
        "score": str(pd[5]) if not pdWhiteList and pd[0].source != "Dietas" else "0",
        "np": pd[6].notdefault if pd[6] is not None else False,
        "am": pd[6].antimicro if pd[6] is not None else False,
        "av": pd[6].mav if pd[6] is not None else False,
        "c": pd[6].controlled if pd[6] is not None else False,
        "q": pd[6].chemo if pd[6] is not None else False,
        "alergy": bool(pd[0].allergy == "S"),
        "allergy": bool(pd[0].allergy == "S"),
        "whiteList": pdWhiteList,
        "recommendation": pd[0].notes,
    }


@has_permission(Permission.WRITE_PRESCRIPTION)
def update_prescription_drug_data(
    id_prescription_drug: int, data: dict, user_context: User
):
    drug = (
        db.session.query(PrescriptionDrug)
        .filter(PrescriptionDrug.id == id_prescription_drug)
        .first()
    )
    if drug is None:
        raise ValidationError(
            "Registro inexistente",
            "errors.businessRules",
            status.HTTP_400_BAD_REQUEST,
        )

    if not data_authorization_service.has_segment_authorization(
        id_segment=drug.idSegment, user=user_context
    ):
        raise ValidationError(
            "Usuário não autorizado neste segmento",
            "errors.unauthorized",
            status.HTTP_401_UNAUTHORIZED,
        )

    if "notes" in data:
        notes = data.get("notes", None)
        idDrug = data.get("idDrug", None)
        admissionNumber = data.get("admissionNumber", None)

        note = (
            db.session.query(Notes)
            .filter(Notes.idPrescriptionDrug == id_prescription_drug)
            .first()
        )
        newObs = False

        if note is None:
            newObs = True
            note = Notes()
            note.idPrescriptionDrug = id_prescription_drug
            note.idOutlier = 0

        note.idDrug = idDrug
        note.admissionNumber = admissionNumber
        note.notes = notes
        note.update = datetime.today()
        note.user = user_context.id

        if newObs:
            db.session.add(note)

    if "form" in data:
        drug.form = data.get("form", None)
        drug.update = datetime.today()
        drug.user = user_context.id

    return drug.id


# TODO: needs refactor (very confuse)
@has_permission(Permission.READ_PRESCRIPTION)
def get_drug_period(id_prescription_drug: int, future: bool, user_context: User):
    results = [{1: []}]

    if id_prescription_drug != 0:
        results, admissionHistory = _drug_period_query(
            id_prescription_drug, future, is_cpoe=user_context.cpoe()
        )
    else:
        results[0][1].append("Intervenção no paciente não tem medicamento associado.")

    if future and len(results[0][1]) == 0:
        if admissionHistory:
            results[0][1].append("Não há prescrição posterior para esse Medicamento")
        else:
            results[0][1].append("Não há prescrição posterior para esse Paciente")

    if user_context.cpoe() and not future:
        periodList = []

        for i, p in enumerate(results):
            period = p[0]

            period = period.replace("33x", "SNx")
            period = period.replace("44x", "ACMx")
            period = period.replace("55x", "CONTx")
            period = period.replace("66x", "AGORAx")
            period = period.replace("99x", "N/Dx")
            periodList.append(period)
    else:
        periodList = results[0][1]

        for i, p in enumerate(periodList):
            p = p.replace("33x", "SNx")
            p = p.replace("44x", "ACMx")
            p = p.replace("55x", "CONTx")
            p = p.replace("66x", "AGORAx")
            p = p.replace("99x", "N/Dx")
            periodList[i] = p

    return periodList


# TODO: needs refactor (very confuse)
def _drug_period_query(id_prescription_drug: int, future: bool, is_cpoe=False):
    pd = PrescriptionDrug.query.get(id_prescription_drug)
    if pd is None:
        return [{1: []}], None

    p = Prescription.query.get(pd.idPrescription)

    admissionHistory = None

    if future:
        drugHistory = _getDrugFuture(p.id, p.admissionNumber)
        admissionHistory = Prescription.getFuturePrescription(p.id, p.admissionNumber)

        return (
            db.session.query(PrescriptionDrug, drugHistory.label("drugHistory"))
            .filter(PrescriptionDrug.id == id_prescription_drug)
            .all(),
            admissionHistory,
        )

    drugHistory = _getDrugHistory(
        p.id, p.admissionNumber, id_drug=pd.idDrug, is_cpoe=is_cpoe
    )

    if is_cpoe:
        return drugHistory.all(), admissionHistory
    else:
        return (
            db.session.query(PrescriptionDrug, drugHistory.label("drugHistory"))
            .filter(PrescriptionDrug.id == id_prescription_drug)
            .all(),
            admissionHistory,
        )


# TODO: needs refactor (very confuse)
def _getDrugFuture(idPrescription, admissionNumber):
    pd1 = db.aliased(PrescriptionDrug)
    pr1 = db.aliased(Prescription)

    query = (
        db.session.query(
            func.concat(
                pr1.id,
                " = ",
                func.to_char(pr1.date, "DD/MM"),
                " (",
                pd1.frequency,
                "x ",
                pd1.dose,
                " ",
                pd1.idMeasureUnit,
                ") via ",
                pd1.route,
                "; ",
            )
        )
        .select_from(pd1)
        .join(pr1, pr1.id == pd1.idPrescription)
        .filter(pr1.admissionNumber == admissionNumber)
        .filter(pr1.id > idPrescription)
        .filter(pd1.idDrug == PrescriptionDrug.idDrug)
        .filter(pd1.suspendedDate == None)
        .order_by(asc(pr1.date))
        .as_scalar()
    )

    return func.array(query)


# TODO: needs refactor (very confuse)
def _getDrugHistory(idPrescription, admissionNumber, id_drug, is_cpoe):
    pd1 = db.aliased(PrescriptionDrug)
    pr1 = db.aliased(Prescription)

    if is_cpoe == False:
        query = (
            db.session.query(
                func.concat(
                    func.to_char(pr1.date, "DD/MM"),
                    " (",
                    pd1.frequency,
                    "x ",
                    func.trim(func.to_char(pd1.dose, "9G999G999D99")),
                    " ",
                    pd1.idMeasureUnit,
                    ")",
                )
            )
            .select_from(pd1)
            .join(pr1, pr1.id == pd1.idPrescription)
            .filter(pr1.admissionNumber == admissionNumber)
            .filter(pr1.id < idPrescription)
            .filter(pd1.idDrug == PrescriptionDrug.idDrug)
            .filter(pd1.suspendedDate == None)
            .filter(pr1.date > (date.today() - timedelta(days=30)))
            .order_by(asc(pr1.date))
            .as_scalar()
        )

        return func.array(query)
    else:
        sub_qry = (
            db.session.query(
                Prescription.date.label("date"),
                func.max(Prescription.expire).label("expire"),
                func.max(PrescriptionDrug.suspendedDate).label("suspension"),
                PrescriptionDrug.frequency.label("frequency"),
                PrescriptionDrug.dose.label("dose"),
                PrescriptionDrug.idMeasureUnit.label("idMeasureUnit"),
            )
            .select_from(PrescriptionDrug)
            .join(Prescription, Prescription.id == PrescriptionDrug.idPrescription)
            .filter(Prescription.admissionNumber == admissionNumber)
            .filter(PrescriptionDrug.idDrug == id_drug)
            .group_by(
                Prescription.date,
                PrescriptionDrug.frequency,
                PrescriptionDrug.dose,
                PrescriptionDrug.idMeasureUnit,
            )
            .order_by(asc(Prescription.date))
            .subquery()
        )

        cpoeperiods = db.aliased(sub_qry)

        query = db.session.query(
            func.concat(
                func.to_char(cpoeperiods.c.date, "DD/MM"),
                " - ",
                func.to_char(
                    func.coalesce(cpoeperiods.c.suspension, cpoeperiods.c.expire),
                    "DD/MM",
                ),
                " (",
                cpoeperiods.c.frequency,
                "x ",
                func.trim(func.to_char(cpoeperiods.c.dose, "9G999G999D99")),
                " ",
                cpoeperiods.c.idMeasureUnit,
                ")",
                case((cpoeperiods.c.suspension != None, " - suspenso"), else_=""),
            )
        ).select_from(cpoeperiods)

        return query
