from decimal import Decimal, InvalidOperation
from io import BytesIO
import logging
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import PdfSettings, PdfTemplateSettings, PdfTemplateType

logger = logging.getLogger(__name__)


def _text(value):
    if value is None or value == '':
        return '-'
    return str(value)


def _paragraph(value, style):
    safe = escape(_text(value)).replace('\n', '<br/>')
    return Paragraph(safe, style)


def _markup(value, style):
    safe_markup = _text(value).replace('\n', '<br/>')
    return Paragraph(safe_markup, style)


def _bool_label(value):
    return 'Sim' if value else 'Não'


def _image_flowable_from_field(field_file, max_width, max_height, h_align='LEFT'):
    """Return a ReportLab Image from a Django ImageField/FileField.

    Prefer local filesystem paths when available, but fall back to reading bytes
    through Django storage. This keeps PDF logos working with local media,
    mounted volumes and remote storages.
    """
    if not field_file or not getattr(field_file, 'name', ''):
        return None

    try:
        try:
            image_path = Path(field_file.path)
        except (AttributeError, NotImplementedError, ValueError):
            image_path = None

        if image_path and image_path.exists():
            image_source = str(image_path)
        else:
            field_file.open('rb')
            try:
                data = field_file.read()
            finally:
                field_file.close()
            if not data:
                return None
            image_source = BytesIO(data)

        img = Image(image_source)
        if isinstance(image_source, BytesIO):
            img._mm_image_source = image_source
        if not img.imageWidth or not img.imageHeight:
            return None
        ratio = min(max_width / img.imageWidth, max_height / img.imageHeight)
        img.drawWidth = img.imageWidth * ratio
        img.drawHeight = img.imageHeight * ratio
        img.hAlign = h_align
        return img
    except Exception:
        logger.exception('Erro ao renderizar imagem %s no PDF.', getattr(field_file, 'name', ''))
        return None


def _logo_candidates(pdf_settings=None, site=None):
    candidates = []
    if pdf_settings and getattr(pdf_settings, 'logo', None):
        candidates.append(('logo configurado em PDFs', pdf_settings.logo))
    if site and getattr(site, 'logo', None):
        candidates.append(('logo da oficina', site.logo))
    return candidates


def _logo_flowable(pdf_settings, site=None, max_width=2.9 * cm, max_height=2.1 * cm):
    if site is None:
        site = _get_site_settings()

    for source_label, field_file in _logo_candidates(pdf_settings, site):
        logo = _image_flowable_from_field(field_file, max_width, max_height)
        if logo:
            return logo
        logger.warning('Logo não pôde ser carregado no PDF: %s.', source_label)

    return Paragraph('', ParagraphStyle(name='BlankLogo', fontSize=1, leading=1))


def _add_configured_header(story, styles, settings, template, site=None):
    if site is None:
        site = _get_site_settings()

    logo = _logo_flowable(settings, site=site, max_width=4.5 * cm, max_height=2.0 * cm)
    if not isinstance(logo, Paragraph):
        story.append(logo)
        story.append(Spacer(1, 0.15 * cm))
    if settings.cabecalho_global:
        story.append(_paragraph(settings.cabecalho_global, styles['SmallMuted']))
        story.append(Spacer(1, 0.15 * cm))
    if template.cabecalho:
        story.append(_paragraph(template.cabecalho, styles['SmallMuted']))
        story.append(Spacer(1, 0.15 * cm))


def _add_configured_footer(story, styles, settings, template):
    footer_blocks = []
    if template.notas_rodape:
        footer_blocks.append(template.notas_rodape)
    if settings.rodape_global:
        footer_blocks.append(settings.rodape_global)
    if not footer_blocks:
        return
    story.append(Spacer(1, 0.35 * cm))
    story.append(Table([['']], colWidths=[17 * cm], rowHeights=[0.01 * cm], style=[
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
    ]))
    story.append(Spacer(1, 0.2 * cm))
    for block in footer_blocks:
        story.append(_paragraph(block, styles['SmallMuted']))
        story.append(Spacer(1, 0.12 * cm))



WORK_ORDER_DEFAULT_NOTES = """CARO CLIENTE, PREZANDO NOSSO BOM RELACIONAMENTO, É NECESSÁRIO ESTAR CIENTE DE ALGUMAS SITUAÇÕES; PARA ISSO, LISTAMOS ALGUMAS INFORMAÇÕES IMPORTANTES:

- FORNECEMOS GARANTIA DE 90 DIAS DE TODOS OS SERVIÇOS EXECUTADOS PELA OFICINA;
- NÃO FORNECEMOS GARANTIA DE PEÇAS COMPRADAS PELO CLIENTE;
- AO NECESSITAR EXECUTAR NOVO SERVIÇO, DEVIDO A ALGUM PROBLEMA DE PEÇA FORNECIDA PELO CLIENTE, ISSO SERÁ COBRADO;
- GARANTIA DE PEÇAS POR 90 DIAS, SE ADQUIRIDAS NA OFICINA;
- NO CASO DA NECESSIDADE DE ACIONAR A GARANTIA, O CLIENTE DEVERÁ ENTRAR EM CONTATO PARA AGENDAR O REPARO;
- PARA ASSEGURAR O SEU DIREITO DA GARANTIA, O CARRO PASSARÁ POR UMA ANÁLISE TÉCNICA PARA VALIDAR AS POSSÍVEIS CAUSAS DO PROBLEMA RELATADO;
- A MANUTENÇÃO FEITA NO PERÍODO DE GARANTIA POR OUTRO PROFISSIONAL/OFICINA PODERÁ INVALIDAR A GARANTIA.

AGRADECEMOS A CONFIANÇA EM NOSSO TRABALHO."""


def _money(value):
    if value is None or value == '':
        amount = Decimal('0.00')
    else:
        try:
            amount = Decimal(str(value)).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            amount = Decimal('0.00')
    formatted = f'{amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {formatted}'


def _date_time(value):
    if not value:
        return '-'
    try:
        return timezone.localtime(value).strftime('%d/%m/%Y às %H:%M')
    except Exception:
        return _text(value)


def _get_site_settings():
    try:
        from website.models import SiteSettings
        return SiteSettings.get_solo()
    except Exception:
        logger.exception('Erro ao carregar configurações do site para PDF da OS.')
        return None


def _site_value(site, *names):
    for name in names:
        value = getattr(site, name, '') if site else ''
        if value:
            return value
    return ''


def _phone_line(site):
    phones = []
    for name in ('telefone_principal', 'telefone_secundario'):
        value = _site_value(site, name)
        if value:
            phones.append(value)
    return ' / '.join(phones)


def _field(label, value, styles):
    return _markup(f'<b>{escape(_text(label))}</b><br/>{escape(_text(value))}', styles['Field'])


def _section(title, styles):
    table = Table([[_paragraph(title.upper(), styles['SectionBarText'])]], colWidths=[18.0 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e9e9e9')),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return table


def _thin_line_table(data, col_widths, styles, header=True, align_right_cols=()):
    table = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    table_style = [
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#bdbdbd')),
    ]
    if header:
        table_style.extend([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ])
    for col in align_right_cols:
        table_style.append(('ALIGN', (col, 0), (col, -1), 'RIGHT'))
    table.setStyle(TableStyle(table_style))
    return table


def _work_order_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='PdfSmall', parent=styles['Normal'], fontSize=7.8, leading=9.2, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='PdfTiny', parent=styles['Normal'], fontSize=6.8, leading=8.0, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='PdfSmallBold', parent=styles['PdfSmall'], fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='PdfCenterBold', parent=styles['PdfSmallBold'], alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='PdfRight', parent=styles['PdfSmall'], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='Field', parent=styles['Normal'], fontSize=8.2, leading=9.4, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='SectionBarText', parent=styles['PdfCenterBold'], fontSize=8.4, leading=9.5))
    styles.add(ParagraphStyle(name='TableCell', parent=styles['Normal'], fontSize=8.0, leading=9.6, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='TableHeader', parent=styles['TableCell'], fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='TotalLabel', parent=styles['Normal'], fontSize=8.6, leading=10, fontName='Helvetica-Bold', alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='GrandTotal', parent=styles['Normal'], fontSize=15, leading=18, fontName='Helvetica-Bold', alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='Terms', parent=styles['Normal'], fontSize=7.3, leading=8.7, wordWrap='CJK'))
    return styles


def _vehicle_display(order):
    vehicle = order.veiculo
    if not vehicle:
        return '-'
    parts = [_text(vehicle.placa), _text(vehicle.marca), _text(vehicle.modelo)]
    if getattr(vehicle, 'versao', ''):
        parts.append(_text(vehicle.versao))
    return ' - '.join(part for part in parts if part and part != '-')


def _checkin_for_order(order):
    try:
        return order.checkins.filter(ativo=True, excluido_em__isnull=True).first()
    except Exception:
        try:
            return next(iter(order.checkins.all()), None)
        except Exception:
            return None


def _work_order_service_rows(order, styles):
    rows = []
    effective_budget = order.get_effective_approval_budget()
    if effective_budget:
        budget_items = effective_budget.itens.filter(
            tipo__in=['service', 'combo'],
            aprovado=True,
            parent__isnull=True,
        ).order_by('hierarquia_ordem', 'pk')
        for index, item in enumerate(budget_items, start=1):
            prefix = item.codigo or f'S{index}'
            name = f'<b>{escape(_text(prefix))}</b> - {escape(_text(item.nome))}'
            rows.append([
                _markup(name, styles['TableCell']),
                _paragraph(_money(item.subtotal), styles['TableCell']),
            ])
        return rows

    for index, item in enumerate(order.servicos_os.select_related('service').all(), start=1):
        service = item.service
        prefix = service.codigo or f'S{index}'
        name = f'<b>{escape(_text(prefix))}</b> - {escape(_text(service.nome))}'
        rows.append([
            _markup(name, styles['TableCell']),
            _paragraph(_money(item.subtotal), styles['TableCell']),
        ])
    offset = len(rows)
    for index, item in enumerate(order.combos_os.select_related('combo').all(), start=1):
        combo = item.combo
        prefix = combo.codigo or f'C{index + offset}'
        name = f'<b>{escape(_text(prefix))}</b> - {escape(_text(combo.nome))}'
        rows.append([
            _markup(name, styles['TableCell']),
            _paragraph(_money(item.subtotal), styles['TableCell']),
        ])
    return rows


def _work_order_part_rows(order, styles):
    rows = []
    for index, row in enumerate(order.get_stock_requirements(), start=1):
        if not row.get('is_billable_to_customer'):
            continue
        item = row['item']
        unit = getattr(getattr(item, 'unidade', None), 'sigla', '') or 'UN'
        code = item.sku or f'P{index}'
        rows.append([
            _markup(f'<b>{escape(_text(code))}</b> - {escape(_text(item.nome))}', styles['TableCell']),
            _paragraph(f'{row.get("quantidade", 0)},00 {escape(unit)}', styles['TableCell']),
            _paragraph(_money(row.get('valor_unitario')), styles['TableCell']),
            _paragraph(_money(row.get('subtotal')), styles['TableCell']),
        ])
    return rows


def _draw_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.HexColor('#666666'))
    canvas.drawRightString(A4[0] - 1.2 * cm, 0.7 * cm, f'Página {doc.page}')
    canvas.restoreState()


def generate_work_order_pdf(order):
    """Generate a client-facing work order PDF inspired by the compact OS layout."""
    pdf_settings = PdfSettings.get_solo()
    template_settings = PdfTemplateSettings.get_for(PdfTemplateType.ORCAMENTO)
    site = _get_site_settings()
    checkin = _checkin_for_order(order)
    styles = _work_order_styles()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
        title=f'OS {order.codigo}',
    )
    story = []

    shop_name = _site_value(site, 'nome_fantasia') or 'MotorMind'
    shop_address = _site_value(site, 'endereco_completo')
    shop_phones = _phone_line(site)
    shop_email = _site_value(site, 'email_contato', 'email_oficina')

    header_left = _logo_flowable(pdf_settings, site=site)
    header_middle = [
        _markup(f'<b>{escape(shop_name.upper())}</b>', styles['PdfCenterBold']),
        _paragraph(shop_address or '', styles['PdfSmall']),
    ]
    header_right_lines = [line for line in [shop_phones, shop_email.upper() if shop_email else '', pdf_settings.cabecalho_global.strip()] if line]
    header_right = _markup('<br/>'.join(escape(line) for line in header_right_lines), styles['PdfRight'])
    header_table = Table([[header_left, header_middle, header_right]], colWidths=[3.2 * cm, 8.4 * cm, 6.4 * cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(header_table)

    issued_at = timezone.localtime(timezone.now()).strftime('%d/%m/%Y às %H:%M')
    title_row = Table([
        [
            _markup(f'<b>OS: {escape(_text(order.codigo))}</b>', styles['PdfSmallBold']),
            _markup('<b>VIA CLIENTE</b>', styles['PdfCenterBold']),
            _markup(f'<b>Emissão: {issued_at}</b>', styles['PdfRight']),
        ]
    ], colWidths=[4.5 * cm, 6.0 * cm, 7.5 * cm])
    title_row.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e9e9e9')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(title_row)
    story.append(Spacer(1, 0.22 * cm))

    customer = order.cliente
    vehicle = order.veiculo
    data_rows = [
        [
            _field('Nome do cliente', customer.nome_razao_social, styles),
            _field('Telefones', getattr(customer, 'whatsapp', '') or '-', styles),
            _field('Email', getattr(customer, 'email', '') or '-', styles),
            _field('CPF/CNPJ', getattr(customer, 'documento', '') or '-', styles),
        ],
        [
            _field('Placa', getattr(vehicle, 'placa', '') if vehicle else '-', styles),
            _field('Fabricante', getattr(vehicle, 'marca', '') if vehicle else '-', styles),
            _field('Modelo', ' '.join(part for part in [getattr(vehicle, 'modelo', ''), getattr(vehicle, 'versao', '')] if part) if vehicle else '-', styles),
            _field('Ano', getattr(vehicle, 'fipe_ano_codigo', '') if vehicle else '-', styles),
        ],
        [
            _field('Motor', getattr(vehicle, 'codigo_fipe', '') if vehicle else '-', styles),
            _field('Portas', getattr(vehicle, 'qtd_portas', '') if vehicle else '-', styles),
            _field('Combustível', vehicle.get_combustivel_display() if vehicle and getattr(vehicle, 'combustivel', '') else '-', styles),
            _field('KM', order.km_atual or (checkin.km if checkin else getattr(vehicle, 'km', '')) or '-', styles),
        ],
        [
            _field('Tanque', checkin.get_nivel_combustivel_display() if checkin and checkin.nivel_combustivel else '-', styles),
            _field('Direção', vehicle.get_tipo_direcao_display() if vehicle and getattr(vehicle, 'tipo_direcao', '') else '-', styles),
            _field('Ar', 'Sim' if vehicle and getattr(vehicle, 'ar_condicionado', False) else '-', styles),
            _field('Data de entrada', _date_time(order.data_abertura), styles),
        ],
        [
            _field('Veículo', _vehicle_display(order), styles),
            _field('Data de retirada', _date_time(order.data_finalizacao) if order.data_finalizacao else '-', styles),
            _field('Status', order.get_status_display(), styles),
            _field('Técnico', getattr(order.tecnico_responsavel, 'nome_razao_social', '') or getattr(order.tecnico_responsavel, 'email', '') or '-', styles),
        ],
    ]
    data_table = Table(data_rows, colWidths=[4.5 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm])
    data_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#9ca3af')),
    ]))
    story.append(data_table)
    story.append(Spacer(1, 0.12 * cm))

    story.append(_section('Informações de diagnósticos', styles))
    diagnosis_text = order.diagnostico or order.problema_relatado or '-'
    story.append(Table([
        [_markup('<b>Diagnóstico</b>', styles['TableHeader'])],
        [_paragraph(diagnosis_text, styles['TableCell'])],
    ], colWidths=[18 * cm], style=[
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#bdbdbd')),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(Spacer(1, 0.12 * cm))

    service_rows = _work_order_service_rows(order, styles)
    if service_rows:
        story.append(_section('Informações de serviços', styles))
        data = [[_paragraph('Serviço(s)', styles['TableHeader']), _paragraph('Total', styles['TableHeader'])]] + service_rows
        story.append(_thin_line_table(data, [15.9 * cm, 2.1 * cm], styles, header=True, align_right_cols=(1,)))
        story.append(Spacer(1, 0.12 * cm))

    part_rows = _work_order_part_rows(order, styles)
    if part_rows:
        story.append(_section('Informações de peças', styles))
        data = [[
            _paragraph('Peça(s)', styles['TableHeader']),
            _paragraph('Qtd', styles['TableHeader']),
            _paragraph('Valor unit.', styles['TableHeader']),
            _paragraph('Valor total', styles['TableHeader']),
        ]] + part_rows
        story.append(_thin_line_table(data, [12.7 * cm, 1.5 * cm, 1.8 * cm, 2.0 * cm], styles, header=True, align_right_cols=(1, 2, 3)))
        story.append(Spacer(1, 0.18 * cm))

    totals_row = Table([
        [
            _markup(f'<b>Total Serviço(s):</b> {_money(order.subtotal_servicos + order.subtotal_combos)}', styles['TotalLabel']),
            _markup(f'<b>Total Peça(s):</b> {_money(order.subtotal_pecas)}', styles['TotalLabel']),
            _markup(f'Valor total: {_money(order.valor_total)}', styles['GrandTotal']),
        ]
    ], colWidths=[5.6 * cm, 5.6 * cm, 6.8 * cm])
    totals_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(totals_row)

    if order.valor_desconto:
        story.append(_markup(f'<b>Desconto aplicado:</b> {_money(order.valor_desconto)}', styles['PdfRight']))
    story.append(Spacer(1, 0.25 * cm))

    notes = WORK_ORDER_DEFAULT_NOTES
    if template_settings.notas_rodape and template_settings.notas_rodape.strip() not in notes:
        notes = f'{notes}\n\n{template_settings.notas_rodape.strip()}'
    if pdf_settings.rodape_global and pdf_settings.rodape_global.strip() not in notes:
        notes = f'{notes}\n\n{pdf_settings.rodape_global.strip()}'
    story.append(_paragraph(notes, styles['Terms']))
    story.append(Spacer(1, 0.42 * cm))

    signature_rows = []
    if template_settings.mostrar_assinatura_cliente or pdf_settings.mostrar_assinatura_cliente_padrao:
        signature_rows.append([_markup('<b>Assinatura do cliente na retirada do veículo:</b>', styles['PdfRight']), _paragraph('_______________________________', styles['PdfSmall'])])
    if template_settings.mostrar_assinatura_oficina:
        signature_rows.append([_markup('<b>Assinatura da oficina:</b>', styles['PdfRight']), _paragraph('_______________________________', styles['PdfSmall'])])
    if signature_rows:
        sig_table = Table(signature_rows, colWidths=[9.6 * cm, 8.4 * cm], hAlign='RIGHT')
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(sig_table)

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer.getvalue()

def generate_vehicle_checkin_pdf(checkin):
    pdf_settings = PdfSettings.get_solo()
    template_settings = PdfTemplateSettings.get_for(PdfTemplateType.CHECKIN)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f'Check-in {checkin.codigo}',
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SmallMuted', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#666666'), wordWrap='CJK'))
    styles.add(ParagraphStyle(name='SectionTitle', parent=styles['Heading2'], fontSize=13, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name='Cell', parent=styles['Normal'], fontSize=8.5, leading=10.5, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CellLabel', parent=styles['Cell'], textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold'))

    story = []
    _add_configured_header(story, styles, pdf_settings, template_settings)

    title = template_settings.titulo or 'Check-in de recepção do veículo'
    story.append(Paragraph(escape(title), styles['Title']))
    story.append(Paragraph(f'{checkin.codigo} - gerado em {timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")}', styles['SmallMuted']))
    story.append(Spacer(1, 0.35 * cm))

    order = checkin.ordem_servico
    vehicle = checkin.veiculo
    customer = checkin.cliente
    vehicle_label = f'{_text(vehicle.placa)} - {_text(vehicle.marca)} {_text(vehicle.modelo)}'
    if vehicle.versao:
        vehicle_label += f' - {_text(vehicle.versao)}'

    data = [
        [_paragraph('Check-in', styles['CellLabel']), _paragraph(checkin.codigo, styles['Cell'])],
        [_paragraph('OS', styles['CellLabel']), _paragraph(order.codigo, styles['Cell'])],
        [_paragraph('Cliente', styles['CellLabel']), _paragraph(customer.nome_razao_social, styles['Cell'])],
        [_paragraph('E-mail', styles['CellLabel']), _paragraph(customer.email, styles['Cell'])],
        [_paragraph('Veículo', styles['CellLabel']), _paragraph(vehicle_label, styles['Cell'])],
        [_paragraph('Chassi', styles['CellLabel']), _paragraph(vehicle.chassi, styles['Cell'])],
        [_paragraph('Data', styles['CellLabel']), _paragraph(timezone.localtime(checkin.data_checkin).strftime('%d/%m/%Y %H:%M'), styles['Cell'])],
        [_paragraph('KM', styles['CellLabel']), _paragraph(checkin.km, styles['Cell'])],
        [_paragraph('Combustível', styles['CellLabel']), _paragraph(checkin.get_nivel_combustivel_display(), styles['Cell'])],
    ]
    table = Table(data, colWidths=[3.3 * cm, 13.7 * cm], repeatRows=0)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9fafb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    story.append(Paragraph('Itens conferidos', styles['SectionTitle']))
    checked_data = [
        [_paragraph('Item', styles['CellLabel']), _paragraph('Status', styles['CellLabel'])],
        [_paragraph('Estepe', styles['Cell']), _paragraph(_bool_label(checkin.possui_estepe), styles['Cell'])],
        [_paragraph('Macaco', styles['Cell']), _paragraph(_bool_label(checkin.possui_macaco), styles['Cell'])],
        [_paragraph('Chave de roda', styles['Cell']), _paragraph(_bool_label(checkin.possui_chave_roda), styles['Cell'])],
        [_paragraph('Documento do veículo', styles['Cell']), _paragraph(_bool_label(checkin.possui_documento), styles['Cell'])],
    ]
    checked_table = Table(checked_data, colWidths=[8.5 * cm, 8.5 * cm])
    checked_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(checked_table)

    text_blocks = [
        ('Objetos deixados no veículo', checkin.objetos_deixados),
        ('Avarias observadas', checkin.avarias_observadas),
        ('Observações gerais', checkin.observacoes),
    ]
    for block_title, value in text_blocks:
        story.append(Paragraph(block_title, styles['SectionTitle']))
        story.append(_paragraph(value or '-', styles['Cell']))

    photos = list(checkin.fotos.all())
    if photos:
        story.append(Paragraph('Fotos anexadas ao check-in', styles['SectionTitle']))
        for photo in photos:
            path = Path(photo.imagem.path)
            if not path.exists():
                continue
            try:
                img = Image(str(path))
                max_width = 15.5 * cm
                max_height = 8.5 * cm
                ratio = min(max_width / img.imageWidth, max_height / img.imageHeight)
                img.drawWidth = img.imageWidth * ratio
                img.drawHeight = img.imageHeight * ratio
                story.append(img)
                story.append(Paragraph(escape(photo.legenda or path.name), styles['SmallMuted']))
                story.append(Spacer(1, 0.25 * cm))
            except Exception:
                logger.exception('Erro ao renderizar foto %s no PDF de check-in.', photo.pk)
                story.append(Paragraph(f'Foto não pôde ser renderizada no PDF: {escape(path.name)}', styles['SmallMuted']))

    if template_settings.mostrar_assinatura_cliente or template_settings.mostrar_assinatura_oficina:
        story.append(Spacer(1, 0.6 * cm))
        if template_settings.mostrar_assinatura_cliente:
            story.append(Paragraph('Assinatura do cliente: ________________________________________________', styles['Normal']))
            story.append(Spacer(1, 0.35 * cm))
        if template_settings.mostrar_assinatura_oficina:
            story.append(Paragraph('Assinatura da recepção: ______________________________________________', styles['Normal']))

    _add_configured_footer(story, styles, pdf_settings, template_settings)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
