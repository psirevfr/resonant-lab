"""Single byte-range responses so HTML audio can seek between A/B sources."""
import re
from fastapi.responses import Response


def wav_response(data: bytes, range_header: str | None = None) -> Response:
    headers = {'Accept-Ranges': 'bytes', 'Cache-Control': 'private, no-store'}
    if range_header:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header.strip())
        if match and any(match.groups()):
            first, last = match.groups()
            start = int(first) if first else max(0, len(data) - int(last))
            end = min(int(last), len(data) - 1) if first and last else len(data) - 1
            if start >= len(data) or end < start:
                return Response(status_code=416, headers={**headers, 'Content-Range': f'bytes */{len(data)}'})
            headers['Content-Range'] = f'bytes {start}-{end}/{len(data)}'
            return Response(data[start:end + 1], status_code=206, media_type='audio/wav', headers=headers)
        # Ignore unsupported multi-range or malformed headers, serving the file.
    return Response(data, media_type='audio/wav', headers=headers)
