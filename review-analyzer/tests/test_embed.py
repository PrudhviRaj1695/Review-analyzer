"""Unit tests for app.embed: embedding shape and cosine similarity ranking."""
from app.embed import cosine_similarity, embed_texts, retrieve_relevant_reviews
from app.models import Review


def test_embed_texts_returns_one_vector_of_floats_per_input(monkeypatch):
    class FakeEmbeddingItem:
        def __init__(self, vector):
            self.embedding = vector

    class FakeResponse:
        data = [FakeEmbeddingItem([0.1, 0.2, 0.3]), FakeEmbeddingItem([0.4, 0.5, 0.6])]

    class FakeEmbeddings:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        embeddings = FakeEmbeddings()

    monkeypatch.setattr("app.embed.get_llm_client", lambda: FakeClient())

    vectors = embed_texts(["great fit", "runs narrow"])

    assert len(vectors) == 2
    assert all(isinstance(v, list) for v in vectors)
    assert all(isinstance(x, float) for v in vectors for x in v)
    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embed_texts_empty_input_returns_empty_list():
    assert embed_texts([]) == []


def test_cosine_similarity_identical_vectors_is_one():
    v = [1.0, 2.0, 3.0]
    assert round(cosine_similarity(v, v), 9) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_opposite_vectors_is_negative_one():
    assert round(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), 9) == -1.0


def test_cosine_similarity_ranks_similar_text_above_different_text():
    """Mimics real embeddings: two vectors pointing a similar direction score
    higher than a vector pointing a very different direction, regardless of
    magnitude (cosine similarity is direction-only)."""
    grip_review_a = [0.9, 0.8, 0.1]  # "great grip in mud"
    grip_review_b = [0.8, 0.9, 0.2]  # "excellent traction in wet mud" (similar)
    battery_review = [0.1, -0.9, 0.8]  # "battery life is disappointing" (unrelated)

    sim_similar = cosine_similarity(grip_review_a, grip_review_b)
    sim_different = cosine_similarity(grip_review_a, battery_review)

    assert sim_similar > sim_different


def test_retrieve_relevant_reviews_returns_top_k_by_similarity():
    query = [1.0, 0.0]
    close = Review(text="close match", embedding=[0.9, 0.1])
    far = Review(text="far match", embedding=[0.1, 0.9])
    opposite = Review(text="opposite", embedding=[-1.0, 0.0])

    result = retrieve_relevant_reviews([far, opposite, close], query, top_k=2)

    assert result == [close, far]


def test_retrieve_relevant_reviews_skips_reviews_without_embedding():
    query = [1.0, 0.0]
    embedded = Review(text="has embedding", embedding=[1.0, 0.0])
    unembedded = Review(text="no embedding yet", embedding=None)

    result = retrieve_relevant_reviews([unembedded, embedded], query, top_k=5)

    assert result == [embedded]
