from flask import Flask, jsonify
from flask_cors import CORS
import logging
import openai

def create_app(test_config=None):
    """
    Application factory function. This is the main entry point for creating
    and configuring the Flask application.
    """
    import config
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config.Config)

    if test_config is not None:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    CORS(app)

    # Initialize managers within the app context to ensure config is loaded
    with app.app_context():
        from core.care_data_manager import CareDataManager
        from core.vector_data_manager import VectorDataManager
        from .db import get_db
        import json

        openai.api_key = app.config['OPENAI_API_KEY']
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

        def get_patient_data_internal(patient_id):
            """
            Internal function to get patient data directly from the database
            without making an HTTP request. This is used by the CareDataManager.
            """
            db = get_db()
            row = db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
            if not row:
                return None
            patient_data = dict(row)
            patient_data['referred_providers'] = json.loads(patient_data['referred_providers'])
            patient_data['appointments'] = json.loads(patient_data['appointments'])
            patient_data['insurance'] = json.loads(patient_data['insurance'])
            return patient_data

        data_manager = CareDataManager(data_sheet_path=app.config['DATA_SHEET_PATH'], patient_api_base_url=None)
        data_manager.get_patient_data = get_patient_data_internal

        vector_manager = VectorDataManager(app_config=app.config)

        # Store manager instances in the app config for easy access in routes
        app.config['DATA_MANAGER'] = data_manager
        app.config['VECTOR_MANAGER'] = vector_manager
        logging.info("Data managers initialized.")

    # Register database functions (init-db command, close_db)
    from . import db
    db.init_app(app)

    # Register API routes from the routes module
    from . import routes
    app.register_blueprint(routes.bp)

    @app.route('/healthcheck')
    def healthcheck():
        """A simple health check endpoint to confirm the server is running."""
        return jsonify({"status": "ok"})

    return app