import joblib
import boto3
import tempfile
import numpy
import re
from typing import List

from config import Config
from exception.validation_error import ValidationError
from models.prescription import Drug
from utils import status


def get_substance(drugs: List[Drug]):
    if len(drugs) == 0:
        raise ValidationError(
            "Nenhum item selecionado",
            "errors.invalidParams",
            status.HTTP_400_BAD_REQUEST,
        )

    model_subst = _get_model("models/noharm-ml-subst.gz")
    token_subst = _get_model("models/noharm-tk-subst.gz")

    drugs_array = []

    drug_names = []
    for d in drugs:
        drug_names.append(d.name)

    vector = token_subst.transform(drug_names)

    prediction = model_subst.predict(vector)

    for idx, p in enumerate(prediction):
        subst_idx = numpy.where(model_subst.classes_ == p)[0][0]

        subst_prob = model_subst.predict_proba(vector).round(2)[idx][subst_idx]
        drugs_array.append(
            {
                "sctid": p,
                "idDrug": drugs[idx].id,
                "drug": drugs[idx].name,
                "accuracy": subst_prob * 100,
            }
        )

    return drugs_array


def get_factors(conversions):
    if len(conversions) == 0:
        return conversions

    model_factor = _get_model("models/noharm-ml-unit.gz")
    token_med = _get_model("models/noharm-tkm-unit.gz")
    token_unit = _get_model("models/noharm-tku-unit.gz")

    for c in conversions:
        if c["factor"] == None:
            name = re.sub(r"\w{6,}", "", c["name"]).lower()
            measure_unit = c["idMeasureUnit"].lower()

            vector_med = token_med.transform([name])
            vector_unit = token_unit.transform([measure_unit])
            vector_factor = numpy.concatenate(
                (vector_med.toarray(), vector_unit.toarray()), axis=1
            )

            prediction = model_factor.predict(vector_factor)[0]
            factor_idx = numpy.where(model_factor.classes_ == prediction)[0][0]
            factor_prob = model_factor.predict_proba(vector_factor).round(2)[0][
                factor_idx
            ]

            c["prediction"] = prediction
            c["accuracy"] = factor_prob
            c["predictionName"] = name
            c["predictionUnit"] = measure_unit

    return conversions


def _get_client():
    return boto3.client(
        "s3",
        aws_access_key_id=Config.CACHE_BUCKET_ID,
        aws_secret_access_key=Config.CACHE_BUCKET_KEY,
    )


def _get_model(model_name):
    client = _get_client()
    model = None

    with tempfile.TemporaryFile() as f:
        client.download_fileobj(Config.CACHE_BUCKET_NAME, model_name, f)
        f.seek(0)

        model = joblib.load(f)

    return model
