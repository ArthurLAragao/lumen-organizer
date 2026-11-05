"""Publish a plain-text study note, then verify its page. Credentials never saved."""
import re
import requests

from .capture import CaptureError


def publish_note(title, markdown, token, parent_id, session=None):
    parent_id = parent_id.replace('-', '')
    if not re.fullmatch('[a-fA-F0-9]{32}', parent_id):
        raise CaptureError('O identificador da página de destino do Notion é inválido.')
    # API paragraphs keep the source intact without running HTML/embeds.
    parts = [markdown[index:index + 1800] for index in range(0, len(markdown), 1800)]
    if not parts or len(parts) > 90:
        raise CaptureError('Nota vazia ou longa demais para esta publicação.')
    headers = {'Authorization': 'Bearer ' + token, 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
    payload = {'parent': {'page_id': parent_id},
        'properties': {'title': {'type': 'title', 'title': [{'type': 'text', 'text': {'content': title[:200]}}]}},
        'children': [{'object': 'block', 'type': 'paragraph', 'paragraph': {
            'rich_text': [{'type': 'text', 'text': {'content': part}}]}} for part in parts]}
    client = session or requests
    response = client.post('https://api.notion.com/v1/pages', headers=headers, json=payload, timeout=30, allow_redirects=False)
    if response.status_code != 200:
        raise CaptureError('O Notion não confirmou a criação da página.')
    page = response.json()
    identifier = page.get('id', '')
    if not re.fullmatch('[a-fA-F0-9-]{32,36}', identifier):
        raise CaptureError('Identificador de página inesperado.')
    verification = client.get('https://api.notion.com/v1/pages/' + identifier, headers=headers, timeout=30, allow_redirects=False)
    if verification.status_code != 200 or verification.json().get('id') != identifier:
        raise CaptureError('Não foi possível verificar a página publicada.')
    url = page.get('url', '')
    if not url.startswith('https://www.notion.so/') and not url.startswith('https://notion.so/'):
        raise CaptureError('Endereço de página inesperado.')
    return {'id': identifier, 'url': url}
