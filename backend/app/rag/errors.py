"""Safe application errors; external exception messages never become responses."""


class RagError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class EmbeddingInputError(RagError):
    def __init__(self, message: str = "임베딩 입력 형식 또는 토큰 길이를 확인해 주세요."):
        super().__init__(422, "EMBEDDING_INPUT_INVALID", message)


class EmbeddingUnavailable(RagError):
    def __init__(self):
        super().__init__(503, "EMBEDDING_UNAVAILABLE", "임베딩 모델을 사용할 수 없습니다. python -m app.rag.cli prepare-model로 모델을 준비해 주세요.")


class RetrievalConfigurationError(RagError):
    def __init__(self):
        super().__init__(503, "RETRIEVAL_CONFIGURATION_ERROR", "모델·차원·거리 함수·컬렉션 설정을 확인해 주세요.")


class CollectionNotReady(RagError):
    def __init__(self):
        super().__init__(503, "COLLECTION_NOT_READY", "검색 컬렉션이 없습니다. 먼저 지식 데이터를 적재해 주세요.")


class SearchUnavailable(RagError):
    def __init__(self):
        super().__init__(503, "SEARCH_UNAVAILABLE", "검색 서비스를 사용할 수 없습니다.")


class RetrievalTimeout(RagError):
    def __init__(self):
        super().__init__(504, "RETRIEVAL_TIMEOUT", "검색 처리 제한 시간을 초과했습니다.")


class RetrievalDataError(RagError):
    def __init__(self):
        super().__init__(500, "RETRIEVAL_DATA_INVALID", "저장된 검색 데이터가 올바르지 않습니다.")
