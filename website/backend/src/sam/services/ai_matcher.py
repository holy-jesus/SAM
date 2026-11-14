# Re-exporting from matcher.py for full backward compatibility
from sam.services.matcher import (
    clean_process_name,
    compute_string_similarity,
    compute_cosine_similarity,
    generate_embedding,
    extract_path_components,
    match_by_path_and_executable,
    match_raw_process_to_catalog,
    match_by_hash,
    match_by_ru_registry,
    match_by_vector_embedding,
    match_by_wikimedia,
    match_by_openai,
    save_learned_signature,
)

__all__ = [
    "clean_process_name",
    "compute_string_similarity",
    "compute_cosine_similarity",
    "generate_embedding",
    "extract_path_components",
    "match_by_path_and_executable",
    "match_raw_process_to_catalog",
    "match_by_hash",
    "match_by_ru_registry",
    "match_by_vector_embedding",
    "match_by_wikimedia",
    "match_by_openai",
    "save_learned_signature",
]
