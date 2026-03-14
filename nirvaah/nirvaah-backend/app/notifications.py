from twilio.rest import Client
import os

def get_twilio_client():
    return Client(
        os.environ.get('TWILIO_ACCOUNT_SID'),
        os.environ.get('TWILIO_AUTH_TOKEN')
    )

def send_whatsapp(to_phone: str, message: str):
    """Sends a WhatsApp message back to an ASHA worker."""
    client = get_twilio_client()
    sandbox_number = os.environ.get('TWILIO_SANDBOX_NUMBER')
    client.messages.create(
        from_=sandbox_number,
        to=f'whatsapp:{to_phone}',
        body=message
    )
    print(f'[NOTIFY] Sent WhatsApp to {to_phone}')

def build_confirmation(record: dict) -> str:
    """Builds the confirmation message sent back to the ASHA worker."""
    lines = [
        f'*Visit Logged — {record.get("beneficiary_name", "Unknown")}*',
        f'BP: {record.get("bp_systolic", "?")}/{record.get("bp_diastolic", "?")}',
    ]
    if record.get('hemoglobin'):
        hb = record['hemoglobin']
        status = 'Normal' if hb >= 11 else 'Low — Anemia protocol'
        lines.append(f'Hb: {hb} ({status})')
    if record.get('next_visit_date'):
        loc = record.get('next_visit_location', 'PHC')
        lines.append(f'Next visit: {record["next_visit_date"]} at {loc}')
    if record.get('dropout_risk', 0) > 0.70:
        risk = record['dropout_risk']
        lines.append(f'DROPOUT RISK: HIGH ({risk:.2f}) — Follow up before next visit')
    if record.get('eligible_schemes'):
        for scheme in record['eligible_schemes']:
            lines.append(f'Scheme Alert: {scheme["name"]} — Not yet enrolled')
    lines.append(f'Record #{record.get("id", "PENDING")} Synced ✓')
    return '\n'.join(lines)

def build_citizen_update(beneficiary: dict) -> str:
    """Builds a WhatsApp update sent directly to the beneficiary."""
    lines = [
        f'Hello {beneficiary.get("name", "")}! Your health record has been updated.',
        f'Next visit: {beneficiary.get("next_visit_date", "To be scheduled")}',
    ]
    if beneficiary.get('eligible_schemes'):
        lines.append('Your entitlements:')
        for scheme in beneficiary['eligible_schemes']:
            enrolled = scheme.get('enrolled', False)
            s = 'Enrolled' if enrolled else 'Not yet enrolled — ask your ASHA worker'
            lines.append(f'  • {scheme["name"]}: {s}')
    lines.append('Reply RECORD to see your full health history.')
    return '\n'.join(lines)
