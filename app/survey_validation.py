"""
app/survey_validation.py
------------------------
Applies medical rules to extracted survey data to generate alerts/referrals.
"""

def validate_leprosy_survey(extracted: dict) -> dict:
    alerts = []
    for person in extracted.get('rash_details', []):
        if person.get('sensation_test_result') == 'loss_of_sensation':
            alerts.append({
                'flag_type': 'leprosy_referral',
                'severity': 'high',
                'flag_reason': (
                    f"Leprosy suspect: {person.get('person_name', 'unknown')} — "
                    f"rash + loss of sensation confirmed. Refer to PHC immediately."
                ),
            })
    extracted['_referral_alerts'] = alerts
    return extracted


def validate_pulse_polio_survey(extracted: dict) -> dict:
    alerts = []
    if extracted.get('house_marked_for_followup'):
        if extracted.get('guest_children_vaccinated') is False:
            reason = 'unvaccinated guest children present'
        else:
            reason = 'children under 5 not yet vaccinated'
        alerts.append({
            'flag_type': 'polio_followup',
            'severity': 'medium',
            'flag_reason': f"Pulse Polio follow-up required — {reason}.",
        })
    for child in extracted.get('deferred_children', []):
        alerts.append({
            'flag_type': 'polio_deferred',
            'severity': 'low',
            'flag_reason': (
                f"Polio dose deferred for {child.get('person_name', 'child')} "
                f"due to {child.get('reason', 'illness')}. Revisit when recovered."
            ),
        })
    extracted['_referral_alerts'] = alerts
    return extracted


def validate_above_30_survey(extracted: dict) -> dict:
    alerts = []
    referral_count = 0
    for person in extracted.get('screenings', []):
        abnormal_flags = []

        bp_sys = person.get('bp_systolic')
        bp_dia = person.get('bp_diastolic')
        if (bp_sys and bp_sys > 140) or (bp_dia and bp_dia > 90):
            abnormal_flags.append(f"High BP {bp_sys}/{bp_dia} mmHg")

        sugar = person.get('blood_sugar_value')
        sugar_type = person.get('blood_sugar_type')
        if sugar:
            if sugar_type == 'fasting' and sugar > 126:
                abnormal_flags.append(f"High fasting sugar {sugar} mg/dL")
            elif sugar_type in ('random', 'post_prandial') and sugar > 200:
                abnormal_flags.append(f"High {sugar_type} sugar {sugar} mg/dL")

        if person.get('other_complaints'):
            abnormal_flags.append(f"Complaints: {person['other_complaints']}")

        # Referral only if 2 or more abnormal values simultaneously
        if len(abnormal_flags) >= 2:
            person['referred_to_phc'] = True
            person['referral_reason'] = '; '.join(abnormal_flags)
            referral_count += 1
            alerts.append({
                'flag_type': 'above_30_referral',
                'severity': 'high',
                'flag_reason': (
                    f"Refer {person.get('person_name', 'patient')} "
                    f"(age {person.get('age', '?')}) to PHC — {person['referral_reason']}"
                ),
            })

    extracted['referral_count'] = referral_count
    extracted['_referral_alerts'] = alerts
    return extracted


def validate_pregnant_survey(extracted: dict) -> dict:
    # Reuses existing ANC thresholds — flags are already set by Claude in the prompt
    alerts = []
    if extracted.get('referred_to_phc'):
        alerts.append({
            'flag_type': 'pregnant_survey_referral',
            'severity': 'high',
            'flag_reason': (
                f"Pregnant survey referral: "
                f"{extracted.get('beneficiary_name', 'patient')} — "
                f"{extracted.get('referral_reason', 'abnormal vitals detected')}"
            ),
        })
    extracted['_referral_alerts'] = alerts
    return extracted


SURVEY_VALIDATORS = {
    'leprosy':    validate_leprosy_survey,
    'pulse_polio': validate_pulse_polio_survey,
    'above_30':   validate_above_30_survey,
    'pregnant':   validate_pregnant_survey,
}


def validate_survey(extracted: dict) -> dict:
    survey_type = extracted.get('survey_type')
    validator = SURVEY_VALIDATORS.get(survey_type)
    if not validator:
        raise ValueError(f"Unknown survey type: {survey_type}")
    return validator(extracted)
