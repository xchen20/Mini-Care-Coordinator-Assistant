import sqlite3
import click
import os
from flask import current_app, g
import db_utils

def get_db():
    """
    Connects to the application's configured database. The connection
    is unique for each request and will be reused if called again during
    the same request.
    """
    if 'db' not in g:
        # Ensure the database directory exists before connecting
        os.makedirs(os.path.dirname(current_app.config['DATABASE_PATH']), exist_ok=True)
        g.db = sqlite3.connect(
            current_app.config['DATABASE_PATH'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db

def close_db(e=None):
    """Closes the database connection if it was opened for this request."""
    db = g.pop('db', None)

    if db is not None:
        db.close()

@click.command('init-db')
def init_db_command():
    """Flask CLI command to clear existing data and create new tables."""
    db = get_db()
    db_utils.create_tables(db, current_app.config['SCHEMA_PATH'])
    db_utils.seed_data(db, current_app.config['PATIENT_SHEET_PATH'])
    click.echo('Initialized the database.')

def init_app(app):
    """Registers database functions with the Flask application instance."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)