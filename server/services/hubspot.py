"""
HubSpot CRM integration — creates contacts and deals after each analyzed call.

Scopes used (from pat-na2-…):
  crm.objects.contacts.read   — search for existing contact by phone
  crm.objects.contacts.write  — create/update contact
  crm.objects.deals.read      — (not strictly needed in v1 but good to have)
  crm.objects.deals.write     — create deal + store call summary in description

No notes scope needed — call summary goes into the deal's description field.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from server.core.config import HUBSPOT_ACCESS_TOKEN, HUBSPOT_API_BASE


class HubSpotClient:
    """Thin async wrapper around HubSpot CRM v3 API."""

    def __init__(self):
        self._http = httpx.AsyncClient(
            base_url=HUBSPOT_API_BASE,
            headers={
                "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(15.0),
        )

    async def aclose(self):
        await self._http.aclose()

    # ── Contacts ──────────────────────────────────────────────────────────────

    async def find_contact_by_phone(self, phone: str) -> str | None:
        """Search for a contact by phone number. Returns contact id or None."""
        try:
            resp = await self._http.post(
                "/crm/v3/objects/contacts/search",
                json={
                    "filterGroups": [{
                        "filters": [{
                            "propertyName": "phone",
                            "operator": "EQ",
                            "value": phone,
                        }]
                    }],
                    "properties": ["id"],
                    "limit": 1,
                },
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return results[0]["id"] if results else None
        except Exception as e:
            logger.warning(f"hubspot=find_contact_failed phone={phone} error={e!r}")
            return None

    async def create_contact(
        self,
        *,
        name: str | None = None,
        phone: str | None = None,
        city: str | None = None,
        language: str | None = None,
    ) -> str | None:
        """Create a HubSpot contact. Returns contact id or None on failure."""
        properties: dict[str, str] = {}
        if name:
            # HubSpot splits name into firstname/lastname
            parts = name.strip().split(" ", 1)
            properties["firstname"] = parts[0]
            if len(parts) > 1:
                properties["lastname"] = parts[1]
        if phone:
            properties["phone"] = phone
        if city:
            properties["city"] = city
        if language:
            # Store as a custom property — create it in HubSpot if needed
            properties["hs_language"] = language

        try:
            resp = await self._http.post(
                "/crm/v3/objects/contacts",
                json={"properties": properties},
            )
            resp.raise_for_status()
            contact_id = resp.json()["id"]
            logger.info(f"hubspot=contact_created id={contact_id}")
            return contact_id
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                # Contact already exists (conflict) — try to get existing
                logger.info(f"hubspot=contact_already_exists phone={phone}")
                existing_id = await self.find_contact_by_phone(phone or "")
                return existing_id
            logger.error(f"hubspot=create_contact_failed error={e!r}")
            return None
        except Exception as e:
            logger.error(f"hubspot=create_contact_failed error={e!r}")
            return None

    # ── Deals ─────────────────────────────────────────────────────────────────

    async def create_deal(
        self,
        *,
        contact_id: str | None = None,
        lead_name: str | None = None,
        budget_range: str | None = None,
        property_type: str | None = None,
        city: str | None = None,
        timeline: str | None = None,
        call_summary: str | None = None,
        call_id: str | None = None,
        lead_score: float | None = None,
    ) -> str | None:
        """
        Create a HubSpot deal linked to the contact.
        Call summary stored in deal description (no notes scope needed).
        Returns deal id or None.
        """
        deal_name = f"Lead: {lead_name or 'Unknown'} — {city or 'Unknown City'}"

        # Build description from call data
        desc_parts: list[str] = []
        if budget_range:
            desc_parts.append(f"Budget: {budget_range}")
        if property_type:
            desc_parts.append(f"Property: {property_type}")
        if timeline:
            desc_parts.append(f"Timeline: {timeline}")
        if lead_score is not None:
            desc_parts.append(f"Lead score: {lead_score}")
        if call_id:
            desc_parts.append(f"Rasen call ID: {call_id}")
        if call_summary:
            desc_parts.append(f"\nCall summary:\n{call_summary}")

        properties: dict[str, Any] = {
            "dealname": deal_name,
            "dealstage": "appointmentscheduled",  # First stage in default pipeline
            "pipeline": "default",
            "description": "\n".join(desc_parts),
        }

        try:
            resp = await self._http.post(
                "/crm/v3/objects/deals",
                json={"properties": properties},
            )
            resp.raise_for_status()
            deal_id = resp.json()["id"]
            logger.info(f"hubspot=deal_created id={deal_id}")

            # Associate deal to contact if we have one
            if contact_id:
                await self._associate_deal_contact(deal_id, contact_id)

            return deal_id
        except Exception as e:
            logger.error(f"hubspot=create_deal_failed error={e!r}")
            return None

    async def _associate_deal_contact(self, deal_id: str, contact_id: str) -> None:
        """Associate a deal with a contact using CRM associations API."""
        try:
            resp = await self._http.put(
                f"/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/deal_to_contact",
            )
            resp.raise_for_status()
            logger.info(f"hubspot=deal_contact_associated deal={deal_id} contact={contact_id}")
        except Exception as e:
            logger.warning(f"hubspot=associate_failed deal={deal_id} contact={contact_id} error={e!r}")


# ── Singleton ─────────────────────────────────────────────────────────────────
_client: HubSpotClient | None = None


def get_hubspot_client() -> HubSpotClient:
    global _client
    if _client is None:
        _client = HubSpotClient()
    return _client


async def close_hubspot_client():
    global _client
    if _client:
        await _client.aclose()
        _client = None


# ── High-level sync helper ────────────────────────────────────────────────────

async def sync_call_to_hubspot(
    call_id: str,
    extraction: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[str | None, str | None]:
    """
    Top-level function: given Rasen extracted data + metadata,
    create/find a HubSpot contact and create a deal.
    Returns (contact_id, deal_id).
    """
    if not HUBSPOT_ACCESS_TOKEN:
        logger.warning("hubspot=skipped reason=HUBSPOT_ACCESS_TOKEN_not_set")
        return None, None

    hs = get_hubspot_client()

    caller_name = extraction.get("caller_name") or extraction.get("name")
    caller_phone = extraction.get("caller_phone") or metadata.get("caller_phone")
    city = extraction.get("city_preference") or extraction.get("city")
    language = extraction.get("detected_language") or extraction.get("language")
    budget = extraction.get("budget_range") or extraction.get("budget")
    prop_type = extraction.get("property_type")
    timeline = extraction.get("timeline")

    # Find or create contact
    contact_id = None
    if caller_phone:
        contact_id = await hs.find_contact_by_phone(caller_phone)

    if not contact_id:
        contact_id = await hs.create_contact(
            name=caller_name,
            phone=caller_phone,
            city=city,
            language=language,
        )

    # Create deal
    deal_id = await hs.create_deal(
        contact_id=contact_id,
        lead_name=caller_name,
        budget_range=budget,
        property_type=prop_type,
        city=city,
        timeline=timeline,
        call_summary=extraction.get("call_summary"),
        call_id=call_id,
        lead_score=extraction.get("lead_score"),
    )

    return contact_id, deal_id
