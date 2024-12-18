import requests
import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models.main import User, dbSession, db
from models.appendix import SchemaConfig
from exception.validation_error import ValidationError
from utils import status

# TODO: refactor
app_names = Blueprint("app_names", __name__)


@app_names.route("/names/<int:idPatient>", methods=["GET"])
@jwt_required()
def proxy_name(idPatient):
    user = User.find(get_jwt_identity())
    dbSession.setSchema(user.schema)

    config = _get_config(user)
    token = _get_token(config)

    url = config["getname"]["url"]
    params = dict(config["getname"]["params"], **{"cd_paciente": idPatient})

    try:
        response = requests.get(
            url,
            headers={"Authorization": token},
            params=params,
        )

        if response.status_code == status.HTTP_200_OK:
            data = response.json()

            if len(data["data"]) > 0:
                patient = data["data"][0]

                return {
                    "status": "success",
                    "idPatient": patient["idPatient"],
                    "name": patient["name"],
                }, status.HTTP_200_OK

        logging.basicConfig()
        logger = logging.getLogger("noharm.backend")
        logger.error(f"Service names ERROR: {response.status_code}")
        logger.error(url)
        logger.error(params)
        logger.error(response.json())
    except Exception as e:
        logging.basicConfig()
        logger = logging.getLogger("noharm.backend")
        logger.error("Service names ERROR (exception)")
        logger.error(url)
        logger.error(params)
        logger.exception(e)

    return {
        "status": "error",
        "idPatient": int(idPatient),
        "name": f"Paciente {str(int(idPatient))}",
    }, status.HTTP_400_BAD_REQUEST


@app_names.route("/names", methods=["POST"])
@jwt_required()
def proxy_multiple():
    user = User.find(get_jwt_identity())
    dbSession.setSchema(user.schema)

    data = request.get_json()
    ids_list = data.get("patients", [])
    config = _get_config(user)
    token = _get_token(config)

    url = config["getname"]["url"]
    params = dict(
        config["getname"]["params"],
        **{"cd_paciente": " ".join(str(id) for id in ids_list)},
    )

    try:
        response = requests.get(url, headers={"Authorization": token}, params=params)

        found = []
        names = []
        if response.status_code == status.HTTP_200_OK:
            data = response.json()

            for p in data["data"]:
                found.append(str(p["idPatient"]))
                names.append(
                    {
                        "status": "success",
                        "idPatient": p["idPatient"],
                        "name": p["name"],
                    }
                )
        else:
            logging.basicConfig()
            logger = logging.getLogger("noharm.backend")
            logger.error(f"Service names error {response.status_code}")
            logger.error(response.json())

    except Exception as e:
        logging.basicConfig()
        logger = logging.getLogger("noharm.backend")
        logger.error(f"Service names ERROR (exception)")
        logger.error(url)
        logger.error(params)
        logger.exception(e)

    for id_patient in ids_list:
        if str(id_patient) not in found:
            names.append(
                {
                    "status": "error",
                    "idPatient": int(id_patient),
                    "name": "Paciente " + str(int(id_patient)),
                }
            )

    return names, status.HTTP_200_OK


def _get_token(config):
    token_url = config["getname"]["token"]["url"]
    params = config["getname"]["token"]["params"]

    response = requests.post(url=token_url, data=params)

    if response.status_code != status.HTTP_200_OK:
        raise ValidationError(
            "Token inválido",
            "errors.unauthorizedUser",
            response.status_code,
        )

    token_data = response.json()

    return token_data["access_token"]


def _get_config(user: User):
    schema_config = (
        db.session.query(SchemaConfig)
        .filter(SchemaConfig.schemaName == user.schema)
        .first()
    )

    if schema_config.config == None or "getname" not in schema_config.config:
        raise ValidationError(
            "Getname sem configuração",
            "errors.invalid",
            status.HTTP_400_BAD_REQUEST,
        )

    return schema_config.config
