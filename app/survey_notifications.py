"""
app/survey_notifications.py
---------------------------
Builds confirmation and alert messages for survey sessions.
"""

def build_survey_confirmation(extracted: dict, survey_type: str) -> str:
    label = {
        'leprosy':    'Leprosy Survey',
        'pulse_polio': 'Pulse Polio Survey',
        'above_30':   'Above 30 Screening',
        'pregnant':   'Pregnant Ladies Survey',
    }.get(survey_type, 'Survey')

    lines = [f'*{label} Logged ✓*']

    if survey_type == 'leprosy':
        lines.append(f"Members screened: {extracted.get('total_members_screened', '—')}")
        lines.append(f"Rashes found: {extracted.get('members_with_rashes', 0)}")
        r = extracted.get('referral_count', 0)
        if r:
            lines.append(f"⚠️ {r} person(s) referred to PHC — rash + sensation loss confirmed")

    elif survey_type == 'pulse_polio':
        lines.append(f"Children under 5: {extracted.get('children_under_5_count', '—')}")
        lines.append(f"Vaccinated today: {extracted.get('children_vaccinated', '—')}")
        if extracted.get('house_marked_for_followup'):
            lines.append('📌 House marked for follow-up visit')
        d = extracted.get('deferred_count', 0)
        if d:
            lines.append(f"⏳ {d} child(ren) deferred — revisit when recovered")

    elif survey_type == 'above_30':
        lines.append(f"People screened: {extracted.get('total_screened', '—')}")
        r = extracted.get('referral_count', 0)
        if r:
            lines.append(f"⚠️ {r} person(s) referred to PHC — 2+ abnormal vitals")

    elif survey_type == 'pregnant':
        lines.append(f"Beneficiary: {extracted.get('beneficiary_name', '—')}")
        if extracted.get('anemia_flag'):
            lines.append(f"⚠️ Anemia — Hb {extracted.get('hemoglobin')} g/dL (below 11)")
        if extracted.get('hypertension_flag'):
            lines.append(f"⚠️ Hypertension — BP {extracted.get('bp_systolic')}/{extracted.get('bp_diastolic')} mmHg")
        if extracted.get('referred_to_phc'):
            lines.append('🚨 Refer to PHC immediately')

    lines.append(f"Record synced ✓")
    return '\n'.join(lines)


def build_worker_referral_alert(extracted: dict, survey_type: str) -> str | None:
    alerts = extracted.get('_referral_alerts', [])
    high_alerts = [a for a in alerts if a['severity'] == 'high']
    if not high_alerts:
        return None
    lines = ['🚨 *Referral Required*']
    for a in high_alerts:
        lines.append(f"→ {a['flag_reason']}")
    lines.append('Please send the patient to the nearest PHC now.')
    return '\n'.join(lines)


def build_supervisor_referral_alert(extracted: dict, survey_type: str, worker_name: str) -> str | None:
    alerts = extracted.get('_referral_alerts', [])
    high_alerts = [a for a in alerts if a['severity'] == 'high']
    if not high_alerts:
        return None
    label = survey_type.replace('_', ' ').title()
    lines = [f'⚠️ *{label} Referral Alert*', f'Worker: {worker_name}']
    for a in high_alerts:
        lines.append(f"• {a['flag_reason']}")
    return '\n'.join(lines)
