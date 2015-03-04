from logging import getLogger
from ploneintranet.docconv.client.fetcher import fetchPreviews

logger = getLogger(__name__)


def queueConversionJob(context, request=None):
    if request is None:
        request = context.REQUEST
    virtual_url_parts = request.get('VIRTUAL_URL_PARTS')
    vr_path = list(request.get('VirtualRootPhysicalPath', ()))
    fetchPreviews.delay(context, virtual_url_parts, vr_path)
    return True
