from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import io
import os
import zipfile
from xml.etree import ElementTree as ET


class InventoryXmlImportError(ValueError):
    """Raised when an uploaded XML/ZIP cannot be parsed as an inventory import source."""


@dataclass
class ParsedXmlSupplier:
    nome: str = ''
    documento: str = ''
    cidade: str = ''
    uf: str = ''


@dataclass
class ParsedXmlProduct:
    document_index: int
    line_index: int
    codigo: str
    codigo_barras: str
    nome: str
    ncm: str
    cest: str
    cfop: str
    unidade_sigla: str
    quantidade: str
    quantidade_original: str
    preco_unitario: str
    valor_total: str
    tipo_sugerido: str
    descricao: str


@dataclass
class ParsedInventoryXml:
    filename: str
    numero: str
    chave: str
    fornecedor: ParsedXmlSupplier
    produtos: list[ParsedXmlProduct]

    def to_dict(self):
        data = asdict(self)
        data['fornecedor'] = asdict(self.fornecedor)
        data['produtos'] = [asdict(produto) for produto in self.produtos]
        return data


UNIT_ALIASES = {
    'UN': 'UN',
    'UND': 'UN',
    'UNID': 'UN',
    'UNIDADE': 'UN',
    'PC': 'PC',
    'PÇ': 'PC',
    'PCA': 'PC',
    'PECA': 'PC',
    'PEÇA': 'PC',
    'PCS': 'PC',
    'CX': 'CX',
    'CAIXA': 'CX',
    'JG': 'JG',
    'JOGO': 'JG',
    'PAR': 'PAR',
    'LT': 'L',
    'L': 'L',
    'LITRO': 'L',
    'ML': 'ML',
    'KG': 'KG',
    'KILO': 'KG',
    'QUILO': 'KG',
    'G': 'G',
    'GR': 'G',
    'M': 'M',
    'MT': 'M',
    'MTS': 'M',
    'CM': 'CM',
}

INSUMO_UNITS = {'L', 'ML', 'KG', 'G', 'M', 'CM'}


def _local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _children(element, name: str):
    return [child for child in list(element) if _local_name(child.tag) == name]


def _first_child(element, name: str):
    for child in list(element):
        if _local_name(child.tag) == name:
            return child
    return None


def _find_first(element, name: str):
    if _local_name(element.tag) == name:
        return element
    for child in element.iter():
        if _local_name(child.tag) == name:
            return child
    return None


def _text(element, path: str, default: str = '') -> str:
    current = element
    for part in path.split('/'):
        current = _first_child(current, part)
        if current is None:
            return default
    return (current.text or '').strip()


def _clean_code(value: str) -> str:
    value = (value or '').strip()
    if value.upper() in {'SEM GTIN', 'SEMGTIN', 'ISENTO', 'N/A', 'NA', '0'}:
        return ''
    return value[:60]


def _decimal_text(value: str, default: str = '0.00') -> str:
    text = (value or '').strip().replace(',', '.')
    try:
        return str(Decimal(text).quantize(Decimal('0.01')))
    except (InvalidOperation, ValueError):
        return default


def _quantity_text(value: str) -> tuple[str, str]:
    original = (value or '').strip().replace(',', '.')
    try:
        amount = Decimal(original)
    except (InvalidOperation, ValueError):
        return '0', original

    if amount < 0:
        amount = Decimal('0')

    # O estoque atual do sistema trabalha com quantidades inteiras. Ao importar XML
    # com quantidade fracionada, arredondamos para cima para não subestimar estoque.
    integer_amount = int(amount.to_integral_value(rounding=ROUND_CEILING))
    return str(integer_amount), original


def _normalize_unit(value: str) -> str:
    raw = (value or '').strip().upper()
    raw = raw.replace('.', '').replace('-', '').replace(' ', '')
    return UNIT_ALIASES.get(raw, raw[:12] or 'UN')


def _infer_item_type(unit_sigla: str) -> str:
    return 'insumo' if unit_sigla.upper() in INSUMO_UNITS else 'peca'


def _product_description(prod, document_number: str, document_key: str, filename: str) -> str:
    parts = []
    xprod = _text(prod, 'xProd')
    ncm = _text(prod, 'NCM')
    cest = _text(prod, 'CEST')
    cfop = _text(prod, 'CFOP')
    cean = _clean_code(_text(prod, 'cEAN') or _text(prod, 'cEANTrib'))

    if xprod:
        parts.append(xprod)
    metadata = []
    if ncm:
        metadata.append(f'NCM: {ncm}')
    if cest:
        metadata.append(f'CEST: {cest}')
    if cfop:
        metadata.append(f'CFOP: {cfop}')
    if cean:
        metadata.append(f'EAN: {cean}')
    if document_number:
        metadata.append(f'NF-e: {document_number}')
    if document_key:
        metadata.append(f'Chave NF-e: {document_key}')
    metadata.append(f'Fonte: {filename}')
    if metadata:
        parts.append(' | '.join(metadata))
    return '\n'.join(parts)


def _parse_nfe_xml(xml_bytes: bytes, filename: str, document_index: int) -> ParsedInventoryXml:
    if not xml_bytes or not xml_bytes.strip():
        raise InventoryXmlImportError(f'O arquivo {filename} está vazio.')

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise InventoryXmlImportError(f'O arquivo {filename} não é um XML válido: {exc}.') from exc

    inf_nfe = _find_first(root, 'infNFe')
    if inf_nfe is None:
        raise InventoryXmlImportError(f'O arquivo {filename} não parece ser uma NF-e: tag infNFe não encontrada.')

    ide = _first_child(inf_nfe, 'ide')
    emit = _first_child(inf_nfe, 'emit')
    numero = _text(ide, 'nNF') if ide is not None else ''
    chave = (inf_nfe.attrib.get('Id') or '').replace('NFe', '').strip()

    fornecedor = ParsedXmlSupplier()
    if emit is not None:
        ender_emit = _first_child(emit, 'enderEmit')
        fornecedor = ParsedXmlSupplier(
            nome=_text(emit, 'xNome'),
            documento=_text(emit, 'CNPJ') or _text(emit, 'CPF'),
            cidade=_text(ender_emit, 'xMun') if ender_emit is not None else '',
            uf=_text(ender_emit, 'UF') if ender_emit is not None else '',
        )

    produtos = []
    dets = _children(inf_nfe, 'det')
    for line_index, det in enumerate(dets, start=1):
        prod = _first_child(det, 'prod')
        if prod is None:
            continue

        codigo_xml = _clean_code(_text(prod, 'cProd'))
        ean = _clean_code(_text(prod, 'cEAN') or _text(prod, 'cEANTrib'))
        codigo = codigo_xml or ean
        nome = (_text(prod, 'xProd') or codigo or f'Item {line_index}').strip()[:180]
        unidade = _normalize_unit(_text(prod, 'uCom') or _text(prod, 'uTrib'))
        quantidade, quantidade_original = _quantity_text(_text(prod, 'qCom') or _text(prod, 'qTrib'))
        preco_unitario = _decimal_text(_text(prod, 'vUnCom') or _text(prod, 'vUnTrib'))
        valor_total = _decimal_text(_text(prod, 'vProd'))

        produtos.append(ParsedXmlProduct(
            document_index=document_index,
            line_index=line_index,
            codigo=codigo,
            codigo_barras=ean,
            nome=nome,
            ncm=_text(prod, 'NCM'),
            cest=_text(prod, 'CEST'),
            cfop=_text(prod, 'CFOP'),
            unidade_sigla=unidade,
            quantidade=quantidade,
            quantidade_original=quantidade_original,
            preco_unitario=preco_unitario,
            valor_total=valor_total,
            tipo_sugerido=_infer_item_type(unidade),
            descricao=_product_description(prod, numero, chave, filename),
        ))

    return ParsedInventoryXml(
        filename=filename,
        numero=numero,
        chave=chave,
        fornecedor=fornecedor,
        produtos=produtos,
    )


def _iter_xml_payloads(uploaded_file):
    name = getattr(uploaded_file, 'name', '') or 'arquivo.xml'
    raw = uploaded_file.read()
    uploaded_file.seek(0)

    if name.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                xml_names = [
                    filename for filename in archive.namelist()
                    if filename.lower().endswith('.xml') and not filename.endswith('/')
                ]
                if not xml_names:
                    raise InventoryXmlImportError('O ZIP não contém arquivos XML.')
                for filename in xml_names:
                    yield os.path.basename(filename), archive.read(filename)
        except zipfile.BadZipFile as exc:
            raise InventoryXmlImportError('O arquivo enviado não é um ZIP válido.') from exc
        return

    yield os.path.basename(name), raw


def parse_inventory_xml_upload(uploaded_file) -> list[ParsedInventoryXml]:
    documents = []
    errors = []

    for index, (filename, xml_bytes) in enumerate(_iter_xml_payloads(uploaded_file), start=1):
        try:
            document = _parse_nfe_xml(xml_bytes, filename, index)
            documents.append(document)
        except InventoryXmlImportError as exc:
            errors.append(str(exc))

    if not documents:
        detail = ' '.join(errors) if errors else 'Nenhum XML válido foi encontrado.'
        raise InventoryXmlImportError(detail)

    return documents
