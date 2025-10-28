import json
import logging

def create_tables(db, schema_path):
    """Creates database tables from a schema file."""
    logging.info("Creating database tables...")
    with open(schema_path, 'r') as f:
        db.cursor().executescript(f.read())
    db.commit()
    logging.info("Tables created successfully.")

def seed_data(db, patient_sheet_path):
    """Seeds the database with initial patient data."""
    
    # Check if data already exists to prevent duplicate seeding
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(id) FROM patients")
    if cursor.fetchone()[0] > 0:
        logging.info("Database already seeded. Skipping.")
        return

    logging.info("Seeding database with initial data...")

    # Load patient data from the dedicated patient sheet
    try:
        with open(patient_sheet_path, 'r') as f:
            patient_data = json.load(f)
        patients_to_seed = patient_data.get("InitialPatientData", [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Could not load or parse patient_sheet.json for seeding: {e}")
        return

    for patient in patients_to_seed:
        cursor.execute(
            "INSERT INTO patients (id, name, dob, pcp, ehrId, insurance, referred_providers, appointments) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                patient['id'], patient['name'], patient['dob'], patient.get('pcp'), patient.get('ehrId'),
                json.dumps(patient.get('insurance')), json.dumps(patient.get('referred_providers')), json.dumps(patient.get('appointments')),
            )
        )
    
    db.commit()
    logging.info("Database seeded successfully.")