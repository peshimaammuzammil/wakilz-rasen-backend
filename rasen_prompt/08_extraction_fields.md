# Data Extraction Fields
# Set these up in: Rasen Dashboard → Agent → Configuration → Data Extraction
# Add each field manually with the exact name, type, and description below.

---

## Field 1
- **Name**: `lead_name`
- **Type**: Text
- **Description**: Caller's first name as spoken during the call. Empty string if the caller never gave their name.

## Field 2
- **Name**: `discovery_intent`
- **Type**: Selector
- **Options**: `exploring`, `specific_project`, `investment`
- **Description**: Caller's primary intent as detected during qualification. Use `exploring` if they are generally browsing, `specific_project` if they mentioned a particular project, `investment` if they stated investment or rental returns as the goal. Empty if intent was never established.

## Field 3
- **Name**: `preferred_location`
- **Type**: Text
- **Description**: The primary area or locality the caller expressed interest in. e.g. "Kokapet", "Kondapur", "Financial District". If they said multiple areas, use the one they prioritised. Empty if no area preference was stated.

## Field 4
- **Name**: `budget_range`
- **Type**: Text
- **Description**: The budget range as the caller stated it during the call. e.g. "1 to 1.5 crore", "under 1 crore", "above 2 crore". Use the caller's exact phrasing. Empty if budget was never mentioned.

## Field 5
- **Name**: `property_type`
- **Type**: Text
- **Description**: The property configuration the caller expressed interest in. e.g. "3BHK apartment", "4BHK", "2BHK", "villa". Empty if property type was never mentioned.

## Field 6
- **Name**: `timeline`
- **Type**: Text
- **Description**: The caller's purchase or possession timeline as they stated it. e.g. "end of this year", "next year", "2 years", "just exploring". Empty if timeline was never mentioned.

## Field 7
- **Name**: `phone_number`
- **Type**: Text
- **Description**: The 10-digit mobile number the caller provided during the call. Include only the digits as spoken, no formatting. Empty if the caller did not provide a phone number.

## Field 8
- **Name**: `contact_preference`
- **Type**: Text
- **Description**: The caller's stated follow-up preference. e.g. "WhatsApp evening", "call morning", "WhatsApp only". Empty if not stated.

## Field 9
- **Name**: `site_visit_slot`
- **Type**: Text
- **Description**: The specific site visit slot confirmed during the call. e.g. "Saturday 11am", "Sunday 4pm". Empty if no visit was booked.

## Field 10
- **Name**: `booking_status`
- **Type**: Selector
- **Options**: `confirmed`, `whatsapp_only`, `not_interested`, `escalated`, `incomplete`
- **Description**: The final outcome of the call regarding booking. Use `confirmed` if a specific visit slot was agreed. Use `whatsapp_only` if caller agreed to receive details on WhatsApp but did not book a visit. Use `not_interested` if caller clearly declined. Use `escalated` if a complaint/grievance was raised. Use `incomplete` if the call ended before a booking decision was made (e.g., caller hung up mid-qualification).

## Field 11
- **Name**: `objection_raised`
- **Type**: Boolean
- **Description**: True if the caller raised any objection during or after the pitch (price concern, distance, family discussion, construction delay, etc.). False if the call proceeded without any objection.

## Field 12
- **Name**: `language_used`
- **Type**: Selector
- **Options**: `hinglish`, `english`
- **Description**: The language the caller predominantly used during the call. Use `hinglish` if they spoke a mix of Hindi and English, or Hindi only. Use `english` if they spoke exclusively in English.

## Field 13
- **Name**: `call_outcome`
- **Type**: Selector
- **Options**: `lead_captured`, `partial_lead`, `no_lead`, `hung_up_early`, `escalated`
- **Description**: The overall quality of the lead outcome. Use `lead_captured` if phone number + at least 3 qualification fields were captured. Use `partial_lead` if some fields were captured but phone number was not obtained. Use `no_lead` if no meaningful information was captured. Use `hung_up_early` if caller disconnected before qualification began. Use `escalated` if a grievance was raised and the call ended via escalation script.
