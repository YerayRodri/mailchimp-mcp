"""
Mailchimp — Servidor MCP
Gestión completa de campañas, audiencias, templates y reporting.

Credencial:
  MAILCHIMP_API_KEY  →  env var (datacenter extraído del sufijo, e.g. -us17)
"""

import hashlib
import json
import os
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

mcp = FastMCP("mailchimp")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _setup() -> tuple[str, tuple[str, str]]:
    key = os.environ.get("MAILCHIMP_API_KEY", "")
    if not key or "-" not in key:
        raise RuntimeError("MAILCHIMP_API_KEY no configurada (formato: key-usXX)")
    dc = key.rsplit("-", 1)[-1]
    return f"https://{dc}.api.mailchimp.com/3.0", ("any", key)


def _params(**kwargs) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None}


def _get(path: str, **kwargs) -> Any:
    base, auth = _setup()
    r = requests.get(f"{base}{path}", auth=auth, params=_params(**kwargs), timeout=30)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict | None = None) -> Any:
    base, auth = _setup()
    r = requests.post(f"{base}{path}", auth=auth, json=body or {}, timeout=60)
    r.raise_for_status()
    return r.json() if r.content else {"status": "ok"}


def _patch(path: str, body: dict) -> Any:
    base, auth = _setup()
    r = requests.patch(f"{base}{path}", auth=auth, json=body, timeout=30)
    r.raise_for_status()
    return r.json() if r.content else {"status": "ok"}


def _put(path: str, body: dict) -> Any:
    base, auth = _setup()
    r = requests.put(f"{base}{path}", auth=auth, json=body, timeout=30)
    r.raise_for_status()
    return r.json() if r.content else {"status": "ok"}


def _delete(path: str) -> dict:
    base, auth = _setup()
    r = requests.delete(f"{base}{path}", auth=auth, timeout=30)
    if r.status_code == 204 or not r.content:
        return {"status": "deleted"}
    r.raise_for_status()
    return r.json()


def _h(email: str) -> str:
    """MD5 del email en minúsculas — ID de contacto en la API de Mailchimp."""
    return hashlib.md5(email.strip().lower().encode()).hexdigest()


def _build(**kwargs) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None}


def _confirm(action: str, detail: str, confirmed: bool) -> dict | None:
    """
    Guarda para operaciones de envío real o borrado irreversible.

    Devuelve el aviso de confirmación si `confirmed` no es True (sin haber
    hecho ninguna llamada a la API de Mailchimp todavía). Devuelve None si
    `confirmed=True` y se puede proceder. Mismo patrón que `_confirm()` en
    google-ads-write-mcp/gmail-mcp/holded-mcp — añadido 2026-08-30, ver
    docs/APIS.md: hasta entonces ninguna operación de Mailchimp tenía freno
    técnico propio.
    """
    if confirmed:
        return None
    return {
        "requires_confirmation": True,
        "warning": f"Acción sobre audiencia/campaña real: {action}. {detail}",
        "instruction": "Muestra este aviso al usuario y pide confirmación explícita. "
                       "Solo repite la llamada con confirmed=True si el usuario confirma.",
    }


# ── AUDIENCIA ─────────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_lists(count: int = 10, offset: int = 0) -> dict:
    """Lista todas las audiencias (listas) con sus estadísticas: total suscriptores, tasa de apertura media, etc."""
    return _get(
        "/lists",
        count=count,
        offset=offset,
        fields="lists.id,lists.name,lists.stats,lists.date_created,total_items",
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_list_members(
    list_id: str,
    status: str = "subscribed",
    tag: str | None = None,
    count: int = 100,
    offset: int = 0,
) -> dict:
    """
    Devuelve los miembros de una audiencia con sus tags y merge fields.
    status: subscribed | unsubscribed | cleaned | pending | archived
    tag: filtrar por nombre de tag (opcional)
    """
    return _get(
        f"/lists/{list_id}/members",
        status=status,
        tag=tag,
        count=count,
        offset=offset,
        fields="members.email_address,members.status,members.merge_fields,members.tags,members.last_changed,total_items",
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_member(list_id: str, email: str) -> dict:
    """Obtiene todos los datos de un contacto por email: estado, tags, merge fields, fecha de suscripción."""
    return _get(f"/lists/{list_id}/members/{_h(email)}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def upsert_member(
    list_id: str,
    email: str,
    status: str = "subscribed",
    fname: str | None = None,
    lname: str | None = None,
    phone: str | None = None,
    tags: list[str] | None = None,
    merge_fields: dict | None = None,
) -> dict:
    """
    Crea o actualiza un contacto (PUT — nunca duplica).
    status: subscribed | unsubscribed | pending | cleaned
    merge_fields: campos custom adicionales, e.g. {"CIUDAD": "Bilbao", "BIRTHDAY": "1990-05-15"}
    tags: lista de nombres de tags a asignar al crear (para actualizar tags en contacto existente usar update_member_tags)
    """
    mf: dict[str, Any] = merge_fields or {}
    if fname:
        mf["FNAME"] = fname
    if lname:
        mf["LNAME"] = lname
    if phone:
        mf["PHONE"] = phone

    body: dict[str, Any] = {
        "email_address": email.strip().lower(),
        "status_if_new": status,
        "merge_fields": mf,
    }
    if tags:
        body["tags"] = tags

    return _put(f"/lists/{list_id}/members/{_h(email)}", body)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def archive_member(list_id: str, email: str) -> dict:
    """Archiva (desuscribe) un contacto. No es borrado permanente — se puede restaurar."""
    return _delete(f"/lists/{list_id}/members/{_h(email)}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def search_members(query: str, list_id: str | None = None) -> dict:
    """Busca contactos por email, nombre o teléfono en todas las audiencias o solo en una."""
    return _get("/search-members", query=query, list_id=list_id)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_member_activity(list_id: str, email: str) -> dict:
    """Últimos 50 eventos de un contacto: aperturas, clics, bajas, rebotes, envíos."""
    return _get(f"/lists/{list_id}/members/{_h(email)}/activity")


# ── TAGS ──────────────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_tags(list_id: str, name: str | None = None) -> dict:
    """Lista todos los tags de una audiencia. Opcionalmente filtra por nombre parcial."""
    return _get(f"/lists/{list_id}/tag-search", name=name)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def update_member_tags(list_id: str, email: str, tags: list[dict]) -> dict:
    """
    Añade o elimina tags de un contacto existente.
    tags: lista de {name: str, status: "active" | "inactive"}
    Ejemplo: [{"name": "Surf Adultos", "status": "active"}, {"name": "Cliente Nuevo 2025", "status": "inactive"}]
    """
    base, auth = _setup()
    r = requests.post(
        f"{base}/lists/{list_id}/members/{_h(email)}/tags",
        auth=auth,
        json={"tags": tags},
        timeout=30,
    )
    r.raise_for_status()
    return {"status": "ok"} if not r.content else r.json()


# ── MERGE FIELDS ──────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_merge_fields(list_id: str) -> dict:
    """Lista todos los campos personalizados de una audiencia: FNAME, LNAME, PHONE, CIUDAD, BIRTHDAY..."""
    return _get(f"/lists/{list_id}/merge-fields")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def create_merge_field(
    list_id: str,
    name: str,
    field_type: str,
    tag: str | None = None,
    required: bool = False,
    public: bool = True,
) -> dict:
    """
    Crea un campo personalizado en la audiencia.
    field_type: text | number | address | phone | date | birthday | url | zip | radio | dropdown | hidden | textarea
    tag: identificador en mayúsculas para merge tags (e.g. "CIUDAD"). Si no se indica, se genera automáticamente.
    """
    body = _build(name=name, type=field_type, tag=tag, required=required, public=public)
    return _post(f"/lists/{list_id}/merge-fields", body)


# ── SEGMENTOS ─────────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_segments(list_id: str, type: str | None = None, count: int = 50) -> dict:
    """
    Lista los segmentos guardados de una audiencia con sus IDs (necesarios para crear campañas segmentadas).
    type: saved | static
    Los tags de Mailchimp son segmentos de tipo static — úsalos aquí para obtener sus IDs.
    """
    return _get(f"/lists/{list_id}/segments", type=type, count=count)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def create_segment(
    list_id: str,
    name: str,
    conditions: list[dict] | None = None,
    match: str = "any",
    static_member_emails: list[str] | None = None,
) -> dict:
    """
    Crea un segmento en una audiencia.
    Para segmentos estáticos (lista fija de emails): usar static_member_emails.
    Para segmentos por condiciones: usar conditions + match ("any"|"all").
    """
    if static_member_emails:
        return _post(f"/lists/{list_id}/segments", {
            "name": name,
            "static_segment": [e.strip().lower() for e in static_member_emails],
        })
    return _post(f"/lists/{list_id}/segments", {
        "name": name,
        "options": {"match": match, "conditions": conditions or []},
    })


# ── BATCH ─────────────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def batch_upsert_members(list_id: str, members: list[dict]) -> dict:
    """
    Crea o actualiza múltiples contactos en una sola llamada API (mucho más rápido que llamadas individuales).
    Ideal para syncs masivos tipo Checkfront→Mailchimp.

    members: lista de dicts con los campos:
      - email (obligatorio)
      - status: subscribed | unsubscribed (por defecto subscribed si es nuevo)
      - fname, lname, phone (opcionales)
      - merge_fields: dict con campos custom adicionales (opcional)
      - tags: lista de nombres de tags (opcional)

    Devuelve batch_id — usar get_batch_status para monitorizar hasta que termine.
    """
    operations = []
    for m in members:
        email = m["email"].strip().lower()
        mf: dict[str, Any] = m.get("merge_fields", {}) or {}
        if m.get("fname"):
            mf["FNAME"] = m["fname"]
        if m.get("lname"):
            mf["LNAME"] = m["lname"]
        if m.get("phone"):
            mf["PHONE"] = m["phone"]

        body: dict[str, Any] = {
            "email_address": email,
            "status_if_new": m.get("status", "subscribed"),
            "merge_fields": mf,
        }
        if m.get("tags"):
            body["tags"] = m["tags"]

        operations.append({
            "method": "PUT",
            "path": f"/lists/{list_id}/members/{_h(email)}",
            "body": json.dumps(body),
        })

    return _post("/batches", {"operations": operations})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_batch_status(batch_id: str) -> dict:
    """
    Comprueba el estado de una operación batch.
    Devuelve: total_operations, finished_operations, errored_operations, status (pending|preprocessing|started|finalizing|finished).
    """
    return _get(f"/batches/{batch_id}")


# ── CAMPAÑAS ──────────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_campaigns(
    status: str | None = None,
    type: str = "regular",
    list_id: str | None = None,
    count: int = 25,
    offset: int = 0,
) -> dict:
    """
    Lista campañas de la cuenta.
    status: save | paused | schedule | sending | sent
    type: regular | plaintext | absplit | rss | variate
    """
    return _get(
        "/campaigns",
        status=status,
        type=type,
        list_id=list_id,
        count=count,
        offset=offset,
        fields="campaigns.id,campaigns.status,campaigns.settings,campaigns.recipients,campaigns.send_time,campaigns.emails_sent,total_items",
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_campaign(campaign_id: str) -> dict:
    """Obtiene todos los detalles de una campaña: settings, segmento destinatario, estado y estadísticas."""
    return _get(f"/campaigns/{campaign_id}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def create_campaign(
    list_id: str,
    subject_line: str,
    from_name: str,
    reply_to: str,
    type: str = "regular",
    preview_text: str | None = None,
    segment_id: int | None = None,
    template_id: int | None = None,
    folder_id: str | None = None,
) -> dict:
    """
    Crea una nueva campaña en estado borrador.
    type: regular | plaintext | absplit | rss | variate
    segment_id: ID de segmento guardado para limitar el envío (obtenerlo con get_segments)
    template_id: ID de template de Mailchimp como base de contenido (opcional)
    """
    settings = _build(
        subject_line=subject_line,
        preview_text=preview_text,
        from_name=from_name,
        reply_to=reply_to,
        template_id=template_id,
        folder_id=folder_id,
    )
    recipients: dict[str, Any] = {"list_id": list_id}
    if segment_id:
        recipients["segment_opts"] = {"saved_segment_id": segment_id}

    return _post("/campaigns", {"type": type, "settings": settings, "recipients": recipients})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def update_campaign(
    campaign_id: str,
    subject_line: str | None = None,
    preview_text: str | None = None,
    from_name: str | None = None,
    reply_to: str | None = None,
    list_id: str | None = None,
    segment_id: int | None = None,
    folder_id: str | None = None,
) -> dict:
    """
    Actualiza la configuración de una campaña existente (asunto, preview text, from, segmento...).
    Solo se modifican los campos que se pasen — el resto no cambia.
    """
    body: dict[str, Any] = {}
    settings = _build(
        subject_line=subject_line,
        preview_text=preview_text,
        from_name=from_name,
        reply_to=reply_to,
        folder_id=folder_id,
    )
    if settings:
        body["settings"] = settings
    if list_id or segment_id:
        recipients: dict[str, Any] = {}
        if list_id:
            recipients["list_id"] = list_id
        if segment_id:
            recipients["segment_opts"] = {"saved_segment_id": segment_id}
        body["recipients"] = recipients

    return _patch(f"/campaigns/{campaign_id}", body)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def replicate_campaign(campaign_id: str) -> dict:
    """
    Duplica una campaña (en estado saved o sent). El duplicado queda en borrador con los mismos settings y contenido.
    Útil para crear la siguiente campaña de una serie reutilizando estructura y diseño.
    """
    return _post(f"/campaigns/{campaign_id}/actions/replicate")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True))
def delete_campaign(campaign_id: str, confirmed: bool = False) -> dict:
    """Elimina una campaña en borrador. Las campañas ya enviadas no se pueden eliminar. Requiere confirmed=True."""
    aviso = _confirm("eliminar campaña", f"campaign_id={campaign_id}", confirmed)
    if aviso:
        return aviso
    return _delete(f"/campaigns/{campaign_id}")


# ── CONTENIDO Y DISEÑO ────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_campaign_content(campaign_id: str) -> dict:
    """Obtiene el HTML y texto plano actuales de una campaña."""
    return _get(f"/campaigns/{campaign_id}/content")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def set_campaign_content(
    campaign_id: str,
    html: str | None = None,
    plain_text: str | None = None,
    template_id: int | None = None,
    url: str | None = None,
) -> dict:
    """
    Establece el contenido HTML de una campaña. Reemplaza todo el contenido actual.

    html: HTML completo del email.
      Merge tags disponibles: *|FNAME|*, *|UNSUB|*, *|ARCHIVE|*
      Para emails bilingues: sección ES → separador '· · · EUSKERA · · ·' → sección EU
      Max-width: 660px | Fuente: Helvetica Neue | Color primario: #000000

    plain_text: versión texto plano (opcional, Mailchimp puede auto-generarla)
    template_id: usar template de Mailchimp como base en lugar de HTML directo
    url: importar contenido desde una URL externa
    """
    body = _build(html=html, plain_text=plain_text, template_id=template_id, url=url)
    return _put(f"/campaigns/{campaign_id}/content", body)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True))
def send_test_email(
    campaign_id: str,
    test_emails: list[str],
    send_type: str = "html",
    confirmed: bool = False,
) -> dict:
    """
    Envía un email de prueba para revisar el diseño antes del envío real. Requiere confirmed=True.
    send_type: html | plaintext
    Usar siempre para verificar el rendering antes de send_campaign.
    """
    aviso = _confirm("enviar email de prueba",
                      f"campaign_id={campaign_id}, destinatarios={test_emails}", confirmed)
    if aviso:
        return aviso
    return _post(
        f"/campaigns/{campaign_id}/actions/test",
        {"test_emails": test_emails, "send_type": send_type},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_send_checklist(campaign_id: str) -> dict:
    """
    Revisa todos los requisitos antes de enviar: asunto, contenido, from email, lista, enlaces de baja, etc.
    Devuelve items con is_ready y los problemas a resolver.
    Llamar siempre antes de send_campaign para evitar errores de validación.
    """
    return _get(f"/campaigns/{campaign_id}/send-checklist")


# ── ENVÍO ─────────────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True))
def send_campaign(campaign_id: str, confirmed: bool = False) -> dict:
    """
    Envía una campaña inmediatamente a todos sus destinatarios. Requiere confirmed=True.
    Verificar con get_send_checklist antes de llamar a esta herramienta.
    """
    aviso = _confirm("enviar campaña real a todos los destinatarios",
                      f"campaign_id={campaign_id}", confirmed)
    if aviso:
        return aviso
    return _post(f"/campaigns/{campaign_id}/actions/send")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def schedule_campaign(
    campaign_id: str,
    schedule_time: str,
    timezone: str = "Europe/Madrid",
) -> dict:
    """
    Programa el envío de una campaña para una fecha/hora específica.
    schedule_time: ISO 8601 en UTC, e.g. "2026-05-15T08:00:00+00:00"
    """
    return _post(
        f"/campaigns/{campaign_id}/actions/schedule",
        {"schedule_time": schedule_time, "timezoneStr": timezone},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True))
def unschedule_campaign(campaign_id: str, confirmed: bool = False) -> dict:
    """Cancela la programación de una campaña para poder editarla de nuevo. Requiere confirmed=True."""
    aviso = _confirm("cancelar la programación de una campaña", f"campaign_id={campaign_id}", confirmed)
    if aviso:
        return aviso
    return _post(f"/campaigns/{campaign_id}/actions/unschedule")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def create_resend(campaign_id: str) -> dict:
    """
    Crea una campaña de reenvío dirigida a los suscriptores que no abrieron el email original.
    Mailchimp genera automáticamente el segmento de no-aperturas.
    La campaña resultante queda en borrador — editar el asunto antes de enviar.
    """
    return _post(f"/campaigns/{campaign_id}/actions/create-resend")


# ── TEMPLATES ─────────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_templates(count: int = 20, type: str | None = None) -> dict:
    """
    Lista los templates disponibles en la cuenta.
    type: user | base | gallery
    """
    return _get(
        "/templates",
        count=count,
        type=type,
        fields="templates.id,templates.name,templates.type,templates.date_created,total_items",
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def create_template(name: str, html: str, folder_id: str | None = None) -> dict:
    """
    Crea un template reutilizable a partir de HTML.
    Útil para guardar la estructura base del email bilingüe (ES → · · · EUSKERA · · · → EU)
    y reutilizarla en todas las campañas sin partir de cero cada vez.
    """
    body = _build(name=name, html=html, folder_id=folder_id)
    return _post("/templates", body)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def update_template(
    template_id: int,
    name: str | None = None,
    html: str | None = None,
) -> dict:
    """Actualiza el nombre o HTML de un template existente."""
    body = _build(name=name, html=html)
    return _patch(f"/templates/{template_id}", body)


# ── REPORTING ─────────────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_campaign_report(campaign_id: str) -> dict:
    """
    Informe completo de una campaña enviada: aperturas, clics, bajas, rebotes, spam reports.
    Benchmarks PTX: tasa apertura >25% | tasa clic >3% | bajas <0.2%
    """
    return _get(f"/reports/{campaign_id}")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_campaign_advice(campaign_id: str) -> dict:
    """Consejos automáticos de Mailchimp basados en las métricas de la campaña (aperturas, clics, bajas...)."""
    return _get(f"/reports/{campaign_id}/advice")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_campaign_click_details(campaign_id: str) -> dict:
    """Detalle de clics por URL: qué links se hicieron clic, cuántas veces y cuántos suscriptores únicos."""
    return _get(f"/reports/{campaign_id}/click-details")


# ── GESTIÓN DE SEGMENTOS ESTÁTICOS ───────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
def add_members_to_segment(list_id: str, segment_id: int, emails: list[str]) -> dict:
    """
    Añade emails a un segmento estático existente.
    Útil para mantener listas curadas: añadir nuevos alumnos a un segmento sin recrearlo.

    emails: lista de direcciones de email (máx 500 por llamada).
    """
    members_to_add = [e.strip().lower() for e in emails]
    return _post(
        f"/lists/{list_id}/segments/{segment_id}",
        {"members_to_add": members_to_add},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True))
def remove_members_from_segment(list_id: str, segment_id: int, emails: list[str], confirmed: bool = False) -> dict:
    """
    Elimina emails de un segmento estático existente. Requiere confirmed=True.

    emails: lista de direcciones de email a eliminar del segmento.
    """
    aviso = _confirm("eliminar miembros de un segmento",
                      f"list_id={list_id}, segment_id={segment_id}, emails={emails}", confirmed)
    if aviso:
        return aviso
    members_to_remove = [e.strip().lower() for e in emails]
    return _post(
        f"/lists/{list_id}/segments/{segment_id}",
        {"members_to_remove": members_to_remove},
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True))
def delete_segment(list_id: str, segment_id: int, confirmed: bool = False) -> dict:
    """Elimina un segmento guardado. No elimina los contactos, solo el segmento. Requiere confirmed=True."""
    aviso = _confirm("eliminar segmento", f"list_id={list_id}, segment_id={segment_id}", confirmed)
    if aviso:
        return aviso
    return _delete(f"/lists/{list_id}/segments/{segment_id}")


# ── REPORTING AVANZADO ────────────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_campaign_open_details(
    campaign_id: str,
    count: int = 100,
    offset: int = 0,
) -> dict:
    """
    Lista los suscriptores que abrieron una campaña con número de aperturas y fecha.
    Útil para crear segmentos de compradores activos o para targeting de reenvíos.

    Devuelve: email, opens_count, last_open, merge_fields (FNAME...).
    """
    return _get(
        f"/reports/{campaign_id}/open-details",
        count=count,
        offset=offset,
        fields="members.email_address,members.opens_count,members.last_open,members.merge_fields,total_opens,unique_opens,total_items",
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def get_campaign_unsubscribes(campaign_id: str, count: int = 50, offset: int = 0) -> dict:
    """
    Lista los contactos que se dieron de baja tras esta campaña.
    Útil para analizar qué campañas generan más bajas y optimizar el contenido.
    """
    return _get(
        f"/reports/{campaign_id}/unsubscribed",
        count=count,
        offset=offset,
        fields="unsubscribes.email_address,unsubscribes.reason,unsubscribes.timestamp,total_items",
    )


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
