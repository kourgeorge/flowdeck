import os
import chromadb
from chromadb.config import Settings
from openai import OpenAI, AzureOpenAI


class FinancialSituationMemory:
    def __init__(self, name, config):
        if config["backend_url"] == "http://localhost:11434/v1":
            self.embedding = "nomic-embed-text"
        else:
            self.embedding = "text-embedding-3-small"
        
        # Handle Azure OpenAI specially
        if config.get("llm_provider", "").lower() == "azure":
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_api_version = os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
            
            if not azure_endpoint or not azure_api_key:
                raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables must be set for Azure provider")
            
            # For embeddings, Azure uses the same endpoint but with /openai/deployments/{deployment}/embeddings
            # We'll use AzureOpenAI client which handles this properly
            # Timeout prevents indefinite hang if the API is slow or stuck
            self.client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version,
                timeout=120.0,
            )
            # Azure embedding model deployment names use format: text-embedding-3-small-1, text-embedding-3-large-1, etc.
            # Allow override via environment variable, otherwise use Azure deployment name format
            azure_embedding_deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT")
            if azure_embedding_deployment:
                self.embedding = azure_embedding_deployment
            else:
                # Default to Azure deployment name format (text-embedding-3-small-1)
                # Map model names to Azure deployment names
                embedding_model = self.embedding
                if embedding_model == "text-embedding-3-small":
                    self.embedding = "text-embedding-3-small-1"
                elif embedding_model == "text-embedding-3-large":
                    self.embedding = "text-embedding-3-large-1"
                elif embedding_model == "text-embedding-ada-002":
                    self.embedding = "text-embedding-ada-002-2"
                # If custom model, keep as is (user should set AZURE_EMBEDDING_DEPLOYMENT)
        else:
            self.client = OpenAI(base_url=config["backend_url"], timeout=120.0)
        
        self.chroma_client = chromadb.Client(Settings(allow_reset=True))
        # Handle collection creation/getting - use get_or_create pattern
        # First try to get existing collection
        try:
            self.situation_collection = self.chroma_client.get_collection(name=name)
        except Exception:
            # Collection doesn't exist, try to create it
            try:
                self.situation_collection = self.chroma_client.create_collection(name=name)
            except Exception:
                # If creation fails (e.g., collection was created between get and create),
                # try to get it again - handles race conditions
                self.situation_collection = self.chroma_client.get_collection(name=name)

    def get_embedding(self, text):
        """Get OpenAI embedding for a text"""
        
        response = self.client.embeddings.create(
            model=self.embedding, input=text
        )
        return response.data[0].embedding

    def add_situations(self, situations_and_advice):
        """Add financial situations and their corresponding advice. Parameter is a list of tuples (situation, rec)"""

        situations = []
        advice = []
        ids = []
        embeddings = []

        offset = self.situation_collection.count()

        for i, (situation, recommendation) in enumerate(situations_and_advice):
            situations.append(situation)
            advice.append(recommendation)
            ids.append(str(offset + i))
            embeddings.append(self.get_embedding(situation))

        self.situation_collection.add(
            documents=situations,
            metadatas=[{"recommendation": rec} for rec in advice],
            embeddings=embeddings,
            ids=ids,
        )

    def get_memories(self, current_situation, n_matches=1):
        """Find matching recommendations using OpenAI embeddings"""
        query_embedding = self.get_embedding(current_situation)

        results = self.situation_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_matches,
            include=["metadatas", "documents", "distances"],
        )

        matched_results = []
        for i in range(len(results["documents"][0])):
            matched_results.append(
                {
                    "matched_situation": results["documents"][0][i],
                    "recommendation": results["metadatas"][0][i]["recommendation"],
                    "similarity_score": 1 - results["distances"][0][i],
                }
            )

        return matched_results


if __name__ == "__main__":
    # Example usage
    matcher = FinancialSituationMemory()

    # Example data
    example_data = [
        (
            "High inflation rate with rising interest rates and declining consumer spending",
            "Consider defensive sectors like consumer staples and utilities. Review fixed-income portfolio duration.",
        ),
        (
            "Tech sector showing high volatility with increasing institutional selling pressure",
            "Reduce exposure to high-growth tech stocks. Look for value opportunities in established tech companies with strong cash flows.",
        ),
        (
            "Strong dollar affecting emerging markets with increasing forex volatility",
            "Hedge currency exposure in international positions. Consider reducing allocation to emerging market debt.",
        ),
        (
            "Market showing signs of sector rotation with rising yields",
            "Rebalance portfolio to maintain target allocations. Consider increasing exposure to sectors benefiting from higher rates.",
        ),
    ]

    # Add the example situations and recommendations
    matcher.add_situations(example_data)

    # Example query
    current_situation = """
    Market showing increased volatility in tech sector, with institutional investors 
    reducing positions and rising interest rates affecting growth stock valuations
    """

    try:
        recommendations = matcher.get_memories(current_situation, n_matches=2)

        for i, rec in enumerate(recommendations, 1):
            print(f"\nMatch {i}:")
            print(f"Similarity Score: {rec['similarity_score']:.2f}")
            print(f"Matched Situation: {rec['matched_situation']}")
            print(f"Recommendation: {rec['recommendation']}")

    except Exception as e:
        print(f"Error during recommendation: {str(e)}")
