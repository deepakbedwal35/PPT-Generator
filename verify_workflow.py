"""Exercise the real HTTP pipeline. Use --gemini for one live API generation."""
import argparse
import base64
import io
import json
from pathlib import Path
import posixpath
import threading
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import zipfile

import app


def validate_pptx(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        for name in names:
            if name.endswith(('.xml', '.rels')):
                root = ET.fromstring(archive.read(name))
                if name.endswith('.rels'):
                    folder = posixpath.dirname(posixpath.dirname(name))
                    for relation in root:
                        if relation.get('TargetMode') != 'External':
                            target = posixpath.normpath(posixpath.join(folder, relation.get('Target')))
                            assert target in names, (name, target)
        slides = [name for name in names if name.startswith('ppt/slides/slide') and name.endswith('.xml')]
        assert slides
        return len(slides)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gemini', action='store_true')
    args = parser.parse_args()
    app.load_environment()
    output = app.ROOT / 'output' / ('gemini' if args.gemini else 'sample')
    output.mkdir(parents=True, exist_ok=True)
    server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'

    def post(path, value, content_type='application/json', accept='application/json'):
        body = json.dumps(value).encode() if content_type == 'application/json' else value
        request = urllib.request.Request(base + path, data=body, headers={'Content-Type': content_type, 'Accept': accept})
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            message = error.read().decode(errors='replace')
            error.close()
            raise RuntimeError(f'{path}: {message}') from None

    try:
        with urllib.request.urlopen(base + '/') as response:
            assert b'Beamer Deck Maker' in response.read()
        if args.gemini:
            result = json.loads(post('/api/latex', {'brief': 'Explain the water cycle to school students. Three concise slides: overview, processes, and recap. Use standard Beamer, no external images.', 'slideCount': 3}))
            source = result['latex']
        else:
            source = (app.PUBLIC / 'sample.tex').read_text(encoding='utf-8')
        (output / 'main.tex').write_text(source, encoding='utf-8')
        print('Source ready.', flush=True)
        pdf = post('/api/compile', {'latex': source})
        assert pdf.startswith(b'%PDF-')
        (output / 'deck.pdf').write_bytes(pdf)
        print('Compiled PDF.', flush=True)
        result = json.loads(post('/api/pptx', pdf, 'application/pdf'))
        pptx = base64.b64decode(result['pptx'])
        count = validate_pptx(pptx)
        assert count == len(result['slides']) == 3
        (output / 'deck.pptx').write_bytes(pptx)
        for index, preview in enumerate(result['slides'], 1):
            (output / f'slide-{index}.png').write_bytes(base64.b64decode(preview.split(',', 1)[1]))
        # Exercise the binary download contract used by API clients as well.
        binary = post('/api/pptx', pdf, 'application/pdf', app.PPTX_TYPE)
        assert validate_pptx(binary) == count
        print(f'PASS: HTTP source -> PDF -> {count} previews -> PPTX; PDF import and binary download. Artifacts: {output}', flush=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
