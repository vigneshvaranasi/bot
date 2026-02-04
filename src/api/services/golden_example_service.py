"""Golden Example service for managing golden examples with Qdrant integration."""

import logging
from typing import Optional, List, Tuple
from uuid import UUID

from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sqlalchemy import func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.db.models import GoldenExample, User
import src.copilot.config as config

logger = logging.getLogger(__name__)

GOLDEN_EXAMPLES_COLLECTION = "golden_examples"

EMBEDDING_DIMENSION = 384

_embeddings: Optional[HuggingFaceEmbeddings] = None
_qdrant_client: Optional[QdrantClient] = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Get or create the embeddings model"""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def _get_qdrant_client() -> QdrantClient:
    """Get or create the Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        qdrant_url = config.QDRANT_URL
        qdrant_api_key = config.QDRANT_API_KEY

        if not qdrant_url:
            raise ValueError("QDRANT_URL environment variable is not set")

        if qdrant_api_key:
            _qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        else:
            logger.warning("QDRANT_API_KEY not set - connecting without authentication")
            _qdrant_client = QdrantClient(url=qdrant_url)

    return _qdrant_client


def ensure_collection_exists() -> None:
    """Ensure the golden_examples collection exists in Qdrant."""
    client = _get_qdrant_client()
    
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if GOLDEN_EXAMPLES_COLLECTION not in collection_names:
        logger.info(f"Creating Qdrant collection: {GOLDEN_EXAMPLES_COLLECTION}")
        client.create_collection(
            collection_name=GOLDEN_EXAMPLES_COLLECTION,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Created collection: {GOLDEN_EXAMPLES_COLLECTION}")


class GoldenExampleService:
    """Service class for golden example operations with Qdrant integration."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, example_id: UUID) -> Optional[GoldenExample]:
        """Get a golden example by ID."""
        result = await self.session.execute(
            select(GoldenExample).where(GoldenExample.id == example_id)
        )
        return result.scalars().first()

    async def list_examples(
        self,
        limit: int = 20,
        offset: int = 0,
        source_type_filter: Optional[str] = None,
        is_active_filter: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        """
        List golden examples with pagination and filters.
        
        Returns:
            Tuple of (list of examples with creator info, total count)
        """
        base_query = (
            select(GoldenExample, User.email.label("creator_email"))
            .join(User, GoldenExample.created_by == User.id, isouter=True)
        )

        filters = []
        if source_type_filter:
            filters.append(GoldenExample.source_type == source_type_filter)
        if is_active_filter is not None:
            filters.append(GoldenExample.is_active == is_active_filter)
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                GoldenExample.original_query.ilike(search_pattern) |
                GoldenExample.golden_response.ilike(search_pattern)
            )

        if filters:
            base_query = base_query.where(and_(*filters))

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        query = (
            base_query
            .order_by(GoldenExample.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        rows = result.all()

        items = []
        for row in rows:
            example = row[0]
            items.append({
                "id": str(example.id),
                "feedback_id": str(example.feedback_id) if example.feedback_id else None,
                "source_type": example.source_type,
                "approval_type": example.approval_type,
                "original_query": example.original_query,
                "original_response": example.original_response,
                "golden_response": example.golden_response,
                "qdrant_point_id": example.qdrant_point_id,
                "created_by": str(example.created_by) if example.created_by else None,
                "creator_email": row.creator_email,
                "is_active": example.is_active,
                "created_at": example.created_at,
                "updated_at": example.updated_at,
            })

        return items, total

    async def create_example(
        self,
        original_query: str,
        golden_response: str,
        created_by: Optional[UUID] = None,
        original_response: Optional[str] = None,
        feedback_id: Optional[UUID] = None,
        source_type: str = "manual",
        approval_type: str = "manual",
    ) -> GoldenExample:
        """
        Create a new golden example and embed it in Qdrant.
        """
        example = GoldenExample(
            feedback_id=feedback_id,
            source_type=source_type,
            approval_type=approval_type,
            original_query=original_query,
            original_response=original_response or "",
            golden_response=golden_response,
            created_by=created_by,
            is_active=True,
        )
        self.session.add(example)
        await self.session.flush()

        try:
            point_id = await self._embed_example(example)
            example.qdrant_point_id = point_id
        except Exception as e:
            logger.error(f"Failed to embed golden example in Qdrant: {e}")

        await self.session.commit()
        await self.session.refresh(example)

        logger.info(f"Created golden example {example.id} (qdrant_point_id={example.qdrant_point_id})")
        return example

    async def update_example(
        self,
        example_id: UUID,
        golden_response: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[GoldenExample]:
        """
        Update a golden example and re-embed if response changed.
        """
        example = await self.get_by_id(example_id)
        if not example:
            return None

        response_changed = False
        if golden_response is not None and golden_response != example.golden_response:
            example.golden_response = golden_response
            response_changed = True

        if is_active is not None:
            example.is_active = is_active

        if response_changed:
            try:
                if example.qdrant_point_id:
                    await self._delete_from_qdrant(example.qdrant_point_id)
                
                point_id = await self._embed_example(example)
                example.qdrant_point_id = point_id
            except Exception as e:
                logger.error(f"Failed to re-embed golden example: {e}")

        await self.session.commit()
        await self.session.refresh(example)

        return example

    async def delete_example(self, example_id: UUID) -> bool:
        """
        Delete a golden example and remove from Qdrant.
        """
        example = await self.get_by_id(example_id)
        if not example:
            return False

        if example.qdrant_point_id:
            try:
                await self._delete_from_qdrant(example.qdrant_point_id)
            except Exception as e:
                logger.error(f"Failed to delete from Qdrant: {e}")

        await self.session.delete(example)
        await self.session.commit()

        logger.info(f"Deleted golden example {example_id}")
        return True

    async def deactivate_example(self, example_id: UUID) -> Optional[GoldenExample]:
        """Soft-delete by deactivating the example."""
        return await self.update_example(example_id, is_active=False)

    async def _embed_example(self, example: GoldenExample) -> str:
        """
        Embed a golden example in Qdrant.
        
        Returns:
            The Qdrant point ID
        """
        ensure_collection_exists()
        
        embeddings = _get_embeddings()
        client = _get_qdrant_client()

        query_embedding = embeddings.embed_query(example.original_query)

        point_id = str(example.id)

        client.upsert(
            collection_name=GOLDEN_EXAMPLES_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=query_embedding,
                    payload={
                        "original_query": example.original_query,
                        "golden_response": example.golden_response,
                        "source_type": example.source_type,
                        "approval_type": example.approval_type,
                        "is_active": example.is_active,
                        "created_at": example.created_at.isoformat() if example.created_at else None,
                    },
                )
            ],
        )

        logger.debug(f"Embedded golden example {example.id} in Qdrant")
        return point_id

    async def _delete_from_qdrant(self, point_id: str) -> None:
        """Delete a point from Qdrant."""
        client = _get_qdrant_client()
        client.delete(
            collection_name=GOLDEN_EXAMPLES_COLLECTION,
            points_selector=[point_id],
        )
        logger.debug(f"Deleted point {point_id} from Qdrant")

    async def search_similar_examples(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float = 0.5,
    ) -> List[dict]:
        """
        Search for golden examples similar to the given query.
        
        Args:
            query: The user's query to find similar examples for
            top_k: Maximum number of examples to return
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of similar golden examples with scores
        """
        try:
            ensure_collection_exists()
            
            embeddings = _get_embeddings()
            client = _get_qdrant_client()

            query_embedding = embeddings.embed_query(query)

            results = client.search(
                collection_name=GOLDEN_EXAMPLES_COLLECTION,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="is_active",
                            match=MatchValue(value=True),
                        )
                    ]
                ),
            )

            examples = []
            for result in results:
                examples.append({
                    "id": result.id,
                    "score": result.score,
                    "original_query": result.payload.get("original_query"),
                    "golden_response": result.payload.get("golden_response"),
                    "source_type": result.payload.get("source_type"),
                })

            logger.debug(f"Found {len(examples)} similar golden examples for query")
            return examples

        except Exception as e:
            logger.error(f"Error searching golden examples: {e}")
            return []


def search_golden_examples_sync(
    query: str,
    top_k: int = 2,
    score_threshold: float = 0.5,
) -> List[dict]:
    """
    Synchronous version of search for use in LangGraph nodes.
    
    This function can be called directly from the graph without async context.
    """
    try:
        ensure_collection_exists()
        
        embeddings = _get_embeddings()
        client = _get_qdrant_client()

        query_embedding = embeddings.embed_query(query)

        results = client.search(
            collection_name=GOLDEN_EXAMPLES_COLLECTION,
            query_vector=query_embedding,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="is_active",
                        match=MatchValue(value=True),
                    )
                ]
            ),
        )

        examples = []
        for result in results:
            examples.append({
                "id": result.id,
                "score": result.score,
                "original_query": result.payload.get("original_query"),
                "golden_response": result.payload.get("golden_response"),
                "source_type": result.payload.get("source_type"),
            })

        logger.debug(f"[Golden Examples] Found {len(examples)} similar examples for query")
        return examples

    except Exception as e:
        logger.warning(f"[Golden Examples] Error searching: {e}")
        return []


def build_prompt_with_golden_examples(
    base_prompt: str,
    golden_examples: List[dict],
    direct_answer_threshold: float = 0.85,
) -> str:
    """
    Build an enhanced system prompt with golden examples as few-shot examples.
    
    If a golden example has a very high similarity score (above direct_answer_threshold),
    the LLM is instructed that it MAY use that answer directly without calling tools.
    
    Args:
        base_prompt: The original system prompt
        golden_examples: List of golden examples from search (each has 'score' key)
        direct_answer_threshold: Score above which direct answer is allowed (default 0.85)
        
    Returns:
        Enhanced prompt with examples appended
    """
    if not golden_examples:
        return base_prompt

    high_confidence_example = None
    for example in golden_examples:
        if example.get('score', 0) >= direct_answer_threshold:
            high_confidence_example = example
            break

    examples_section = "\n\n## Verified Knowledge from Past Feedback\n\n"
    
    if high_confidence_example:
        examples_section += """
        **Direct Answer Available**
        A verified, admin-approved answer exists for a very similar question. 
        You MAY use the verified response content below WITHOUT calling any tools, 
        but ONLY if the user's question is asking for the SAME information.
        **Rules for using verified answers:**
        - Use the verified response content directly (you can rephrase slightly)
        - Do NOT add any prefix like 'Based on verified knowledge' - just respond naturally
        - If the user asks something DIFFERENT or needs MORE details, use tools as normal
        """        
    else:
        examples_section +=  """
        Here are reference examples of ideal responses for similar questions. 
        Use these as guidance for tone and format only. 
        You should still use tools to retrieve current incident data.\n\n"
        """

    for i, example in enumerate(golden_examples, 1):
        score = example.get('score', 0)
        confidence_label = "HIGH CONFIDENCE" if score >= direct_answer_threshold else "Reference"
        
        examples_section += f"### Example {i} ({confidence_label}, similarity: {score:.0%}):\n"
        examples_section += f"**User Question:** {example['original_query']}\n\n"
        examples_section += f"**Verified Response:** {example['golden_response']}\n\n"

    return base_prompt + examples_section
