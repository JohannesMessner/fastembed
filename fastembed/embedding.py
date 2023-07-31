import os
import shutil
import tarfile
import tempfile
from abc import ABC, abstractmethod
from typing import Any, List

import requests
from tqdm import tqdm


class Embedding(ABC):
    @abstractmethod
    def encode(self, texts):
        pass

class DefaultEmbedding(Embedding):
    def download_file_from_gcs(url, output_path, show_progress=True):
        if os.path.exists(output_path):
            return output_path
        response = requests.get(url, stream=True)

        # Handle HTTP errors
        if response.status_code == 403:
            print("Authentication error: you do not have permission to access this resource.")
            return
        elif response.status_code != 200:
            print(f"HTTP error {response.status_code} while trying to download the file.")
            return

        # Get the total size of the file
        total_size_in_bytes = int(response.headers.get("content-length", 0))

        # Warn if the total size is zero
        if total_size_in_bytes == 0:
            print(f"Warning: Content-length header is missing or zero in the response from {url}.")

        # Initialize the progress bar
        progress_bar = (
            tqdm(total=total_size_in_bytes, unit="iB", unit_scale=True) if total_size_in_bytes and show_progress else None
        )

        # Attempt to download the file
        try:
            with open(output_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):  # Adjust chunk size to your preference
                    if chunk:  # Filter out keep-alive new chunks
                        if progress_bar is not None:
                            progress_bar.update(len(chunk))
                        file.write(chunk)
        except Exception as e:
            print(f"An error occurred while trying to download the file: {str(e)}")
            return
        finally:
            if progress_bar is not None:
                progress_bar.close()
        return output_path

    def decompress_to_cache(targz_path, cache_dir=None):
        # Check if targz_path exists and is a file
        if not os.path.isfile(targz_path):
            raise ValueError(f"{targz_path} does not exist or is not a file.")

        # Check if targz_path is a .tar.gz file
        if not targz_path.endswith(".tar.gz"):
            raise ValueError(f"{targz_path} is not a .tar.gz file.")

        # Create a temporary directory for caching if cache_dir is not provided
        if cache_dir is None:
            cache_dir = tempfile.mkdtemp()

        try:
            # Open the tar.gz file
            with tarfile.open(targz_path, "r:gz") as tar:
                # Extract all files into the cache directory
                tar.extractall(path=cache_dir)
            print(f"Files have been decompressed into {cache_dir}")
        except tarfile.TarError as e:
            # If any error occurs while opening or extracting the tar.gz file,
            # delete the cache directory (if it was created in this function)
            # and raise the error again
            if "tmp" in cache_dir:
                shutil.rmtree(cache_dir)
            raise ValueError(f"An error occurred while decompressing {targz_path}: {e}")

        return cache_dir

    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):        
        filepath = self.download_file_from_gcs(
            "https://storage.googleapis.com/qdrant-fastembed/fast-all-MiniLM-L6-v2.tar.gz", output_path="fast-all-MiniLM-L6-v2.tar.gz"
        )

        model_dir = self.decompress_to_cache(targz_path=filepath)        


class SentenceTransformersEmbedding(Embedding):
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("Please install the sentence-transformers package to use this method.")
        self.model = SentenceTransformer(model_name)

    def encode(self, texts):
        return self.model.encode(texts)

class GeneralTextEmbedding(Embedding):
    """
    https://huggingface.co/thenlper/gte-large

    SoTA embedding model for text based retrieval tasks.
    """

    @classmethod
    def average_pool(last_hidden_states: Any,
                    attention_mask: Any) -> Any:
        last_hidden = last_hidden_states.masked_fill(~attention_mask[..., None].bool(), 0.0)
        return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

    def __init__(self, model_name="thenlper/gte-large"):
        try:
            import torch.nn.functional as F
            from transformers import AutoModel, AutoTokenizer
        except ImportError:
            raise ImportError("Please install the transformers package with torch to use this method.")
        self.tokenizer = AutoTokenizer.from_pretrained("thenlper/gte-large")
        self.model = AutoModel.from_pretrained("thenlper/gte-large")
        
    def encode(self, input_texts: List[str]):
        try:
            import torch.nn.functional as F
        except ImportError:
            raise ImportError("Please install Pytorch to use this method.")
        # Tokenize the input texts
        batch_dict = self.tokenizer(input_texts, max_length=512, padding=True, truncation=True, return_tensors='pt')

        outputs = self.model(**batch_dict)
        embeddings = GeneralTextEmbedding.average_pool(outputs.last_hidden_state, batch_dict['attention_mask'])

        # (Optionally) normalize embeddings
        embeddings = F.normalize(embeddings, p=2, dim=1)
        scores = (embeddings[:1] @ embeddings[1:].T) * 100
        return scores

        

class OpenAIEmbedding(Embedding):
    def __init__(self):
        # Initialize your OpenAI model here
        # self.model = ...
        ...

    def encode(self, texts):
        # Use your OpenAI model to encode the texts
        # return self.model.encode(texts)
        raise NotImplementedError