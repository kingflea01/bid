from app.schemas.common import VersionedRequest


class AnalyzeRequest(VersionedRequest):
    force: bool = False


class MappingRequest(VersionedRequest):
    force: bool = False
