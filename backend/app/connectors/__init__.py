def ingest_all_sources(*args, **kwargs):
    from app.connectors.macro_sources import ingest_all_sources as _ingest_all_sources

    return _ingest_all_sources(*args, **kwargs)


__all__ = ["ingest_all_sources"]

