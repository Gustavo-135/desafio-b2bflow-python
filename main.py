import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv
from supabase import Client, create_client


MAX_CONTACTS = 3
REQUIRED_ENV_VARS = (
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "ZAPI_INSTANCE_ID",
    "ZAPI_INSTANCE_TOKEN",
    "ZAPI_CLIENT_TOKEN",
)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def validate_environment() -> None:
    for name in REQUIRED_ENV_VARS:
        get_required_env(name)


def create_supabase_client() -> Client:
    supabase_url = get_required_env("SUPABASE_URL")
    supabase_key = get_required_env("SUPABASE_KEY")
    return create_client(supabase_url, supabase_key)


def fetch_contacts(supabase: Client) -> list[dict[str, Any]]:
    response = (
        supabase.table("contatos")
        .select("id,nome,telefone")
        .limit(MAX_CONTACTS)
        .execute()
    )

    contacts = response.data or []
    return contacts[:MAX_CONTACTS]


def build_message(contact_name: str) -> str:
    return f"Olá, {contact_name} tudo bem com você?"


def send_zapi_message(phone: str, message: str) -> None:
    instance_id = get_required_env("ZAPI_INSTANCE_ID")
    instance_token = get_required_env("ZAPI_INSTANCE_TOKEN")
    client_token = get_required_env("ZAPI_CLIENT_TOKEN")

    url = (
        f"https://api.z-api.io/instances/{instance_id}"
        f"/token/{instance_token}/send-text"
    )

    payload = {
        "phone": phone,
        "message": message,
    }
    headers = {
        "Client-Token": client_token,
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if not response.ok:
        raise requests.HTTPError(
            f"Z-API retornou status {response.status_code}: {response.text}",
            response=response,
        )


def validate_contact(contact: dict[str, Any]) -> tuple[str, str]:
    name = str(contact.get("nome") or "").strip()
    phone = str(contact.get("telefone") or "").strip()

    if not name:
        raise ValueError("Contato sem nome preenchido")
    if not phone:
        raise ValueError("Contato sem telefone preenchido")

    return name, phone


def main() -> None:
    setup_logging()
    load_dotenv()

    logging.info("Variáveis de ambiente carregadas")

    try:
        validate_environment()
        logging.info("Variáveis obrigatórias validadas")

        logging.info("Conectando ao Supabase")
        supabase = create_supabase_client()

        logging.info("Buscando contatos cadastrados")
        contacts = fetch_contacts(supabase)
    except Exception as exc:
        logging.exception(
            "Erro ao validar ambiente, conectar ou buscar contatos no Supabase: %s",
            exc,
        )
        return

    if not contacts:
        logging.warning("Nenhum contato encontrado no Supabase")
        return

    logging.info("Foram encontrados %s contato(s) para envio", len(contacts))

    for contact in contacts:
        contact_id = contact.get("id", "sem-id")

        try:
            name, phone = validate_contact(contact)
            message = build_message(name)

            logging.info("Enviando mensagem para contato id=%s", contact_id)
            send_zapi_message(phone, message)
            logging.info("Mensagem enviada com sucesso para contato id=%s", contact_id)
        except requests.RequestException as exc:
            response = exc.response
            if response is not None:
                logging.error(
                    "Falha ao enviar mensagem para contato id=%s. Status=%s. Resposta=%s",
                    contact_id,
                    response.status_code,
                    response.text,
                )
                continue

            logging.error(
                "Falha ao enviar mensagem para contato id=%s: %s",
                contact_id,
                exc,
            )
        except Exception as exc:
            logging.error("Contato id=%s ignorado: %s", contact_id, exc)


if __name__ == "__main__":
    main()
