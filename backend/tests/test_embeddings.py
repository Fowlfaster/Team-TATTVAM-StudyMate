import unittest
from unittest.mock import Mock, patch

import numpy as np

from rag.embeddings import embed_query, embed_texts


class EmbeddingTests(unittest.TestCase):
    @patch("rag.embeddings.get_embedding_model")
    def test_embed_texts_returns_l2_normalized_rows(self, get_model: Mock) -> None:
        model = Mock()
        model.embed.return_value = iter([[3.0, 4.0], [0.0, 2.0]])
        get_model.return_value = model

        vectors = embed_texts(["first", "second"])

        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), [1.0, 1.0])
        np.testing.assert_allclose(vectors[0], [0.6, 0.8])
        np.testing.assert_allclose(vectors[1], [0.0, 1.0])
        model.embed.assert_called_once_with(["first", "second"])

    @patch("rag.embeddings.get_embedding_model")
    def test_embed_query_returns_one_normalized_vector(self, get_model: Mock) -> None:
        model = Mock()
        model.embed.return_value = iter([[5.0, 12.0]])
        get_model.return_value = model

        vector = embed_query("query")

        self.assertEqual(vector.shape, (2,))
        np.testing.assert_allclose(vector, [5 / 13, 12 / 13])


if __name__ == "__main__":
    unittest.main()