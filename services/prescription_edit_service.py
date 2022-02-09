from sqlalchemy.orm import make_transient

from models.main import db
from models.appendix import *
from models.prescription import *

from exception.validation_error import ValidationError

def copyPrescription(idPrescription, user):
    roles = user.config['roles'] if user.config and 'roles' in user.config else []
    if ('prescriptionEdit' not in roles):
        raise ValidationError('Usuário não autorizado', 'errors.unauthorizedUser', status.HTTP_401_UNAUTHORIZED)

    prescription = db.session.query(Prescription)\
        .filter(Prescription.id == idPrescription)\
        .first()

    if (prescription is None):
        return False

    db.session.expunge(prescription)
    make_transient(prescription)

    #generate new id
    prescription.id = 6
    prescription.date = datetime.today()
    prescription.expire = datetime.today()
    prescription.status = '0'
    prescription.notes = None
    prescription.notes_at = None
    prescription.agg = None
    prescription.aggDeps = None
    prescription.aggDrugs = None
    prescription.features = None
    prescription.update = datetime.today()
    prescription.user = user.id
    
    db.session.add(prescription)
    db.session.flush()

    pds = db.session.query(PrescriptionDrug)\
        .filter(PrescriptionDrug.idPrescription == idPrescription)\
        .filter(PrescriptionDrug.suspendedDate == None)\
        .all()

    pdArray = []
    pdCount = 0
    for pd in pds:
      db.session.expunge(pd)
      make_transient(pd)

      pd.id = int(str(prescription.id) + "{:03}".format(pdCount))
      pd.idPrescription = prescription.id

      pdCount = pdCount + 1
      pdArray.append(pd)

    db.session.add_all(pdArray)
    db.session.flush()
