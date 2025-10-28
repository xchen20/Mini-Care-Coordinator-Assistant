import json
import requests
from datetime import datetime, timedelta
import logging

# Get a logger specific to this module
logger = logging.getLogger(__name__)
class CareDataManager:
    """
    Manages access to hospital system data (from data_sheet.json)
    and patient-specific data (from Flask API).
    """
    def __init__(self, data_sheet_path, patient_api_base_url):
        self.data_sheet_path = data_sheet_path
        self.patient_api_base_url = patient_api_base_url
        self.hospital_data = self._load_hospital_data()
        self.patient_data_cache = {}
        self._provider_lookup = self._build_provider_lookup()

    def _load_hospital_data(self):
        """Loads the structured hospital data from the JSON file."""
        try:
            with open(self.data_sheet_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Hospital data file not found at {self.data_sheet_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Could not decode JSON from {self.data_sheet_path}")
            return {}

    def _build_provider_lookup(self):
        """Builds a lookup dictionary for fast provider access."""
        lookup = {}
        if not self.hospital_data:
            return lookup
        for provider in self.hospital_data.get("ProviderDirectory", []):
            norm_name, norm_name_alt = self._normalize_provider_name(provider["name"])
            lookup[norm_name] = provider
            lookup[norm_name_alt] = provider
        return lookup

    def get_patient_data(self, patient_id):
        """
        Retrieves patient-specific data. This method is designed to be
        overridden by the app factory to call the database directly.
        """
        if patient_id in self.patient_data_cache:
            return self.patient_data_cache[patient_id]

        try:
            response = requests.get(f"{self.patient_api_base_url}/patient/{patient_id}")
            response.raise_for_status()
            patient_data = response.json()
            self.patient_data_cache[patient_id] = patient_data
            return patient_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching patient data for ID {patient_id}: {e}")
            return None

    def get_provider_info(self, provider_name):
        """
        Retrieves detailed information for a specific provider.
        Handles variations in provider naming (e.g., "Dr. House", "House, Gregory").
        """
        normalized_search_name, normalized_search_name_alt = self._normalize_provider_name(provider_name)
        return self._provider_lookup.get(normalized_search_name) or self._provider_lookup.get(normalized_search_name_alt)

    def _normalize_provider_name(self, name):
        """Normalizes a provider name to 'First Last' and 'Last, First' formats, removing titles."""
        name = name.replace("Dr. ", "").replace(", MD", "").replace(" MD", "").replace(", FNP", "").replace(" FNP", "").replace(", PhD", "").replace(" PhD", "").strip()
        parts = [p.strip() for p in name.replace(',', ' ').split() if p.strip()]
        if not parts:
            return "", ""
        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        return f"{first} {last}".strip(), f"{last}, {first}".strip(", ")

    def get_all_providers(self):
        """Returns a list of all providers."""
        return self.hospital_data.get("ProviderDirectory", [])

    def get_insurance_status(self, payer_name):
        """
        Checks if a given insurance payer is accepted by the hospital.
        """
        if not self.hospital_data:
            return False
        return payer_name in self.hospital_data.get("AcceptedInsurances", [])

    def check_established_patient(self, patient_id, provider_name):
        """
        Determines if a patient is 'ESTABLISHED' with a given provider
        based on appointments in the last 5 years.
        """
        patient_data = self.get_patient_data(patient_id)
        if not patient_data:
            return False

        provider_info = self.get_provider_info(provider_name)
        if not provider_info:
            return False

        search_provider_id = provider_info.get('provider_id')
        five_years_ago = datetime.now() - timedelta(days=5 * 365)

        for appt in patient_data.get("appointments", []):
            if appt.get("status") != "completed":
                continue

            if appt.get("provider_id") == search_provider_id:
                try:
                    appt_date = datetime.fromisoformat(appt["date"])
                    if appt_date >= five_years_ago:
                        return True
                except (ValueError, KeyError):
                    logger.warning(f"Could not parse appointment date: {appt.get('date')}")
        return False