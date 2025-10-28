import chromadb
from chromadb.utils import embedding_functions
import json
import logging

# Get a logger specific to this module
logger = logging.getLogger(__name__)
class VectorDataManager:
    """
    Manages the vector database (ChromaDB) for semantic search.
    Handles creating embeddings and querying for relevant context.
    """
    def __init__(self, app_config):
        self.config = app_config
        self.client = chromadb.PersistentClient(path=self.config['VECTOR_DB_PATH'])
        self.collection_name = self.config['VECTOR_DB_COLLECTION_NAME']

        # Set the embedding function for the collection to ensure consistency.
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=self.config['OPENAI_API_KEY'], # Ensure this is passed from app_config
            model_name=self.config['EMBEDDING_MODEL']
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=openai_ef
        )
        self._index_hospital_data(self.config['DATA_SHEET_PATH'])

    def _index_hospital_data(self, data_sheet_path):
        """
        Loads hospital data, creates embeddings, and stores them in ChromaDB.
        This process is idempotent: it won't re-index if data already exists.
        """
        if self.collection.count() > 0:
            logger.info("ChromaDB collection is already populated. Skipping indexing.")
            return

        logger.info("Indexing hospital data into ChromaDB...")
        try:
            with open(data_sheet_path, 'r') as f:
                hospital_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not load or parse data_sheet.json: {e}")
            return

        documents = []
        metadatas = []
        ids = []
        doc_id = 1

        # Index each provider from the directory as a separate document
        for provider in hospital_data.get("ProviderDirectory", []):
            # Create a detailed description for each department the provider works at
            department_details = []
            for dept in provider.get('departments', []):
                department_details.append(f"Department: {dept.get('name')}, Address: {dept.get('address')}, Hours: {dept.get('hours')}")
            doc_text = f"Provider Information for {provider['name']}: Specialty is {provider['specialty']}. Practice locations and hours are: {'; '.join(department_details)}"
            documents.append(doc_text)
            metadatas.append({"source": "ProviderDirectory", "provider_name": provider['name']})
            ids.append(f"provider_{doc_id}")
            doc_id += 1

        # Index other general rules and policies as documents
        documents.append(f"Appointment Rules: {json.dumps(hospital_data.get('Appointments'))}")
        metadatas.append({"source": "Appointments"})
        ids.append(f"doc_{doc_id}"); doc_id += 1

        documents.append(f"Accepted Insurances: {', '.join(hospital_data.get('AcceptedInsurances', []))}")
        metadatas.append({"source": "AcceptedInsurances"})
        ids.append(f"doc_{doc_id}"); doc_id += 1

        documents.append(f"Self-Pay Rates: {json.dumps(hospital_data.get('SelfPay'))}")
        metadatas.append({"source": "SelfPay"})
        ids.append(f"doc_{doc_id}"); doc_id += 1

        # Add all created documents to the collection. ChromaDB handles embedding.
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        logger.info(f"Successfully indexed {len(documents)} documents into ChromaDB.")

    def query_relevant_context(self, user_prompt, n_results=3):
        """
        Takes a user prompt and queries ChromaDB
        to find the most semantically similar documents.
        """
        # The user_prompt is automatically converted to a vector for querying.
        results = self.collection.query(
            query_texts=[user_prompt],
            n_results=n_results
        )
        return "\n".join(results['documents'][0])